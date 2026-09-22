"""Explicit durable personal data. No model, automatic extraction or tool authority."""
import json
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone

LIMIT = 5
MAX_CONTENT = 500


def database_path():
    from configuration import home
    return Path(os.environ.get('KUZCO_MEMORY_DB', home() / 'kuzco.db'))


def clean(text):
    return ' '.join(text.strip().rstrip('.?!').split())


def subject(content):
    return re.split(r'\s+(?:is|are)\s+', clean(content), maxsplit=1, flags=re.I)[0].casefold()


def credential(text):
    return bool(re.search(r'password|passphrase|api[ _-]?key|(?:auth|access|refresh|bearer)[ _-]?token|private[ _-]?key|secret[ _-]?key|\btoken\b|\bsk-[a-z0-9]|BEGIN .*PRIVATE KEY', text, re.I))


def parse(prompt):
    text = clean(prompt)
    patterns = [('remember', r'(?:please )?remember (?:that )?(.+)'),
                ('forget', r'(?:please )?forget (?:that )?(.+)'),
                ('update', r'(?:please )?update (.+?) to (.+)'),
                ('recall', r'(?:what do you remember|what have you remembered)(?: about (.+))?'),
                ('recall', r'(?:recall|show my memories about) (.+)')]
    for action, pattern in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            return action, tuple(x or '' for x in match.groups())
    if re.match(r'^(?:please )?(?:remember|forget|update|recall)\b', text, re.I):
        return 'invalid', ()
    return None


class MemoryStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else database_path()

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Create with private permissions, including on first use.
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute('CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, content TEXT NOT NULL UNIQUE COLLATE NOCASE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
            connection.execute('CREATE INDEX IF NOT EXISTS memory_subject ON memories(subject)')
            connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(content)')
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def operate(self, action, args):
        from security_log import record
        name = 'memory_' + action if isinstance(action, str) else 'unknown'
        try:
            answer = self._operate(action, args)
            denied = answer.startswith(('Security policy denied', 'Invalid memory', 'Use remember', 'I cannot store', 'Please keep each'))
            failed = denied or answer.startswith('No unique exact memory matched')
            record(name, 'DENY' if denied else 'EXECUTE', 'failure' if failed else 'success')
            return answer
        except Exception:
            record(name, 'EXECUTE', 'failure')
            raise

    def _operate(self, action, args):
        if action not in {'remember', 'recall', 'update', 'forget'}:
            return 'Use remember that …, recall …, update … to …, or forget that ….'
        expected = 2 if action == 'update' else 1
        if not isinstance(args, (tuple, list)) or len(args) != expected or any(not isinstance(x, str) for x in args) or (action != 'recall' and any(not clean(x) for x in args)):
            return 'Invalid memory operation; nothing changed.'
        if any(len(x) > MAX_CONTENT for x in args):
            return 'Please keep each memory or search under 500 characters.'
        if action in {'remember', 'update'} and credential(' '.join(args)):
            return 'I cannot store passwords, keys or authentication credentials in personal memory.'
        from security_policy import require, PolicyError, TOOLS
        name = 'memory_' + action
        try:
            require(name, dict(zip(TOOLS[name].fields, args)))
        except PolicyError:
            return 'Security policy denied this memory operation; nothing changed.'
        db = self.connect()
        try:
            with db:
                now = datetime.now(timezone.utc).isoformat()
                if action == 'remember':
                    content = clean(args[0]); key = subject(content)
                    existing = db.execute('SELECT id, content FROM memories WHERE subject=? OR content=? COLLATE NOCASE LIMIT 2', (key,content)).fetchall()
                    if existing:
                        if len(existing)==1 and existing[0]['content'].casefold()==content.casefold():
                            return 'That memory is already saved.'
                        return 'A memory with that subject already exists. Use update with its exact subject.'
                    row = db.execute('INSERT INTO memories(subject,content,created_at,updated_at) VALUES (?,?,?,?)',(key,content,now,now))
                    db.execute('INSERT INTO memory_search(rowid,content) VALUES (?,?)',(row.lastrowid,content))
                    return 'Memory saved.'
                if action == 'recall':
                    topic = clean(args[0]).casefold()
                    if topic in {'me', 'myself'}:
                        rows = db.execute(
                            'SELECT id,content FROM memories ORDER BY updated_at DESC, id DESC LIMIT ?',
                            (LIMIT,)).fetchall()
                        return ('Stored memories:\n'+'\n'.join(f"[{r['id']}] {r['content']}" for r in rows)) \
                            if rows else 'I have no stored memories about you.'
                    words = re.findall(r'\w+', args[0].casefold())
                    stop = {'my','the','a','about','preferences','preference','memories','that','is','of','and'}
                    terms = [w for w in words if w not in stop][:12]
                    if not terms:
                        return 'Please specify a topic to recall; I do not load all stored memories.'
                    query = ' OR '.join('"'+w+'"*' for w in terms)
                    rows = db.execute('SELECT m.id,m.content FROM memory_search f JOIN memories m ON m.id=f.rowid WHERE memory_search MATCH ? ORDER BY rank LIMIT ?', (query,LIMIT)).fetchall()
                    return ('Stored memories:\n'+'\n'.join(f"[{r['id']}] {r['content']}" for r in rows)) if rows else 'I found no matching stored memories.'
                target = clean(args[0])
                # No fuzzy mutation: exact subject or full saved statement only.
                rows = db.execute('SELECT * FROM memories WHERE subject=? OR content=? COLLATE NOCASE LIMIT 2',(target.casefold(),target)).fetchall()
                if len(rows)!=1:
                    return 'No unique exact memory matched. Please use the exact stored statement or subject; nothing changed.'
                row = rows[0]
                if action == 'forget':
                    db.execute('DELETE FROM memory_search WHERE rowid=?',(row['id'],))
                    db.execute('DELETE FROM memories WHERE id=?',(row['id'],))
                    return 'Memory forgotten.'
                content = row['subject']+' is '+clean(args[1])
                db.execute('UPDATE memories SET content=?,updated_at=? WHERE id=?',(content,now,row['id']))
                db.execute('UPDATE memory_search SET content=? WHERE rowid=?',(content,row['id']))
                return 'Memory updated.'
        finally:
            db.close()


def handle(prompt, personality='default', history=None, debug=False):
    command = parse(prompt)
    if command is None:
        return None
    from personality import personality_context
    personality_context(personality)
    try:
        answer = MemoryStore().operate(*command)
    except (sqlite3.Error, OSError, ValueError):
        answer = 'Personal memory is unavailable right now. Other assistant functions remain available.'
    from direct_response import render_memory
    answer = render_memory(answer, personality)
    # Durable data never includes history; do not copy recalled private data into
    # general tool history where a later web request could transmit it.
    if debug:
        print('[memory]', command[0], '(local SQLite; zero model calls)')
        print('[memory] final answer:', answer)
    return answer
