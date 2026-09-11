"""Replaceable macOS TTS: only accepts the completed human-facing answer."""
import json
import re
import subprocess
from latency import measured


class VoiceOutputError(RuntimeError):
    pass


def spoken_text(answer):
    # Do not vocalize code, JSON-only answers, internal tags, or macOS speech markup.
    text = re.sub(r"```.*?(?:```|$)", "", answer, flags=re.S)
    text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.S | re.I)
    text = re.sub(r"\[\[.*?\]\]", "", text, flags=re.S)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("[debug]"))
    text = text.strip()
    try:
        if isinstance(json.loads(text), (dict, list)):
            return ""
    except ValueError:
        pass
    # Remove embedded JSON objects/arrays too, while leaving ordinary prose/citations.
    decoder = json.JSONDecoder()
    pieces, index = [], 0
    while index < len(text):
        if text[index] in "{[":
            try:
                value, end = decoder.raw_decode(text[index:])
                if isinstance(value, (dict, list)):
                    index += end
                    continue
            except ValueError:
                pass
        pieces.append(text[index])
        index += 1
    text = "".join(pieces).strip()
    # Source links stay in the displayed answer/history, never in Daniel's speech.
    text = re.sub(r"\[[^\]]*\]\(https?://[^\s)]+\)", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r'\[S\d+(?:\.P\d+)?\]', '', text)
    text = re.sub(r"(?im)^\s*(?:research sources?|search sources?|sources?|references?):\s*$", "", text).strip()
    return text


@measured('speech')
def speak(answer, voice_name=None):
    text = spoken_text(answer)
    if not text:
        return False
    try:
        # Text goes through stdin, never a command, option, URL, or filename.
        command = ["/usr/bin/say"]
        if voice_name:
            command += ["-v", voice_name]
        result = subprocess.run(command + ["-f", "-"], input=text,
                                shell=False, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VoiceOutputError("Speech output failed or timed out. The answer remains on screen.") from error
    if result.returncode:
        raise VoiceOutputError("macOS could not speak the answer. Check Sound output settings; the text is preserved.")
    return True
