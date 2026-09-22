"""Conservative whole-utterance Mac controls. No model output becomes authority."""
import re


def parse(prompt):
    if not isinstance(prompt, str):
        return None
    text = ' '.join(prompt.lower().replace('’', "'").split()).strip(' .!?')
    text = re.sub(r'^(?:hey )?(?:kuzco|cuzco|cusco|kusco|kuzko|cuz go)[\s,.!?—:-]+', '', text)
    text = re.sub(r'^please ', '', text)
    text = re.sub(r'^(?:can|could|would) you (?:please )?', '', text)
    text = re.sub(r',? please$', '', text)
    text = re.sub(r',? (?:kuzco|cuzco|cusco|kusco|kuzko)$', '', text)
    # Whisper may repeat a short isolated command. Accept only identical
    # repetitions; mixed commands and explanatory sentences still fall through.
    if re.fullmatch(r'(?:un ?mute)(?:[\s,.;!?]+un ?mute){1,3}', text):
        return 'volume_mute', {'muted': 'false'}
    if re.fullmatch(r'mute(?:[\s,.;!?]+mute){1,3}', text):
        return 'volume_mute', {'muted': 'true'}
    if re.fullmatch(r'(?:quit|close) [a-z][a-z0-9 .\'-]{0,79}', text):
        return 'unsupported_quit', {}
    if re.fullmatch(r'(?:make (?:the )?screen brighter|turn (?:the )?brightness (?:up|down)|'
                    r'turn (?:up|down) (?:the )?(?:display |screen )?brightness|'
                    r'set (?:the )?brightness to [0-9]{1,3}(?: percent|%)?)', text):
        return 'unsupported_brightness', {}
    if re.fullmatch(r'(?:set|start) (?:a |the )?timer(?: for)? .+', text):
        return 'unsupported_timer', {}
    if re.fullmatch(r'(?:play|resume|pause|skip|next) (?:my |the )?.*\b(?:podcast|episode)\b.*', text):
        return 'unsupported_podcast', {}
    if re.fullmatch(r'(?:turn (?:the )?volume (?:up|down)|turn (?:up|down) (?:the )?volume|'
                    r'(?:volume|turn it) (?:up|down)|(?:raise|lower|increase|decrease) (?:the )?volume|'
                    r'make it (?:louder|quieter))', text):
        direction = 'down' if re.search(r'\b(?:down|lower|decrease|quieter)\b', text) else 'up'
        return 'volume_adjust', {'direction': direction}
    match = re.fullmatch(r'(?:set (?:the )?volume to )([0-9]{1,3})(?:\s*(?:percent|%))?', text)
    if match:
        return 'volume_set', {'percent': match[1]}
    if text in {'mute', 'mute the volume', 'mute the sound', 'unmute', 'un mute',
                'unmute the volume', 'unmute the sound', 'unmute it',
                'turn the sound back on', 'turn the volume back on', 'take it off mute'}:
        unmuting = text.startswith(('unmute', 'un mute')) or text in {
            'turn the sound back on', 'turn the volume back on', 'take it off mute'}
        return 'volume_mute', {'muted': 'false' if unmuting else 'true'}
    match = re.fullmatch(r'(?:switch to|focus|bring (?:up|forward)) ([a-z][a-z0-9 .\'-]{0,79})', text)
    if match:
        return 'focus_application', {'application_name': match[1].strip()}
    transport = {'play music': 'play', 'resume music': 'resume', 'resume the music': 'resume',
                 'pause music': 'pause', 'pause the music': 'pause',
                 'skip this song': 'next', 'next track': 'next', 'next song': 'next',
                 'previous track': 'previous', 'previous song': 'previous'}
    if text in transport:
        return 'music_transport', {'action': transport[text]}
    match = re.fullmatch(r'play (?:my |the )?(.+?) playlist', text)
    if match:
        return 'music_play_named', {'kind': 'playlist', 'name': match[1]}
    for kind in ('artist', 'album', 'song', 'track'):
        match = re.fullmatch(r'play (?:the )?(.+?) ' + kind, text)
        if match:
            return 'music_play_named', {'kind': 'song' if kind == 'track' else kind, 'name': match[1]}
    # A bare name could be a song, artist, podcast or something else. Do not
    # silently direct it to Music when Podcasts control is unavailable.
    match = re.fullmatch(r'play ([a-z0-9][a-z0-9 .\'&-]{1,80})', text)
    if match and not re.search(r'\b(?:podcast|episode|video|game|movie)\b', text):
        return 'clarify_media', {}
    return None
