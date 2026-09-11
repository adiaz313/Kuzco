"""Push-to-talk adapter. No personality, tool, or agent decisions live here."""
import sys
import time

from speech_input import LocalSpeechInput, VoiceInputError
from tts_output import speak
from assistant_state import AssistantState, State


def conversation(agent, documents=(), debug=False, max_steps=5, personality="default",
                 seconds=8, device=None, listener=None, speaker=speak, wake=False, state=None):
    state = state if state is not None else AssistantState()
    if listener is None:
        if wake:
            from wake_input import WakeSpeechInput
            listener = WakeSpeechInput(seconds, device)
        else:
            listener = LocalSpeechInput(seconds, device)
    if isinstance(listener, LocalSpeechInput):
        listener.debug = debug
        listener.on_listening = lambda: state.set(State.LISTENING)
        listener.on_thinking = lambda: state.set(State.THINKING)
    listener.check_setup()  # Check dependencies without opening the microphone.
    history = []
    state.set(State.IDLE)
    if wake:
        print(f"Jarvis wake mode ({personality}). Say Kuzco; Ctrl-C exits. Maximum request window: {seconds:g} seconds; ends earlier after speech and silence.")
        print("Microphone monitors locally while idle; off during transcription, thinking, and speaking.")
    else:
        print(f"Jarvis voice ({personality}). Enter records {seconds:g} seconds; /exit quits.")
        print("Microphone is off while waiting, processing, and speaking.")
    while True:
        try:
            if wake:
                print("IDLE — waiting for Kuzco (local microphone on).", flush=True)
            else:
                activation = input("Press Enter to speak: ")
                if activation.strip().lower() in {"/exit", "/quit"}:
                    return
                if activation.strip():
                    print("Press Enter without text to record, or type /exit.")
                    continue
                state.set(State.LISTENING)
                print(f"Recording now for {seconds:g} seconds…", flush=True)
            try:
                transcript = listener.listen().strip()
            except Exception as error:
                print(f"Voice input: {error}", file=sys.stderr)
                if wake:
                    print("Wake mode stopped. Fix microphone setup or use --voice for push-to-talk.")
                    return  # Do not repeatedly reopen a failing microphone.
                continue
            state.set(State.THINKING)
            if transcript:
                print(f"Heard: {transcript}", flush=True)
            if wake:
                from wake_input import request_text
                transcript = request_text(transcript)
            if not transcript:
                print("No recognizable speech. Try again; if this repeats, check microphone permission and input level.")
                continue
            if wake:
                print(f"THINKING — request: {transcript}", flush=True)
            try:
                # The same v0.4 entry point, arguments, history ownership, and step cap.
                answer = agent(transcript, documents=documents, debug=debug,
                               history=history, max_steps=max_steps, personality=personality)
            except Exception as error:
                print(f"Jarvis: Error: {error}", file=sys.stderr)
                continue  # Developer/runtime errors are never passed to TTS.
            print(f"Jarvis: {answer}", flush=True)
            try:
                if wake:
                    print("SPEAKING — microphone off.", flush=True)
                state.set(State.SPEAKING)
                speaker(answer)  # Only the final answer; never messages/debug/tool results.
            except Exception as error:
                print(f"Speech output: {error}", file=sys.stderr)
                # The completed turn stays in history even if playback fails.
            if wake:
                time.sleep(0.35)  # Let speaker/room audio settle before reopening input.
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return
        finally:
            state.set(State.IDLE)
