"""Generate a listening pack of short expressive and multi-speaker clips.

Usage: python tests/voice_samples.py https://POD_ID-8080.proxy.runpod.net [output_dir]
Each clip is saved as a WAV with its timing. Lines are kept short so every request
finishes well inside RunPod's 100-second proxy limit.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

CASES = {
    "01-neutral": "Hello! This is a quick voice test. How do I sound?",
    "02-excited": "[excited] We actually won! I can't believe it!",
    "03-whisper": "[whisper] Don't make a sound. They're right outside the door.",
    "04-angry": "[angry] I told you three times. Why didn't you listen?",
    "05-sad": "[crying] I waited all night... and you never came.",
    "06-laughing": "[laughing] Oh no, you did not just say that!",
    "07-two-speakers": (
        "<|speaker:0|> [excited] Guess what? I finally got the job!\n"
        "<|speaker:1|> [surprised] No way! The one in Tokyo?\n"
        "<|speaker:0|> [laughing] Yes! I start next month.\n"
        "<|speaker:1|> [sad] I'm happy for you. I'm just going to miss you."
    ),
    "08-four-speakers": (
        "<|speaker:0|> [calm] Okay, everyone, quiet. We have five minutes.\n"
        "<|speaker:1|> [nervous] Five minutes? We haven't even started the slides!\n"
        "<|speaker:2|> [laughing] Relax, I finished them last night.\n"
        "<|speaker:3|> [angry] You could have told us that an hour ago!\n"
        "<|speaker:0|> [whisper] Shh. The boss is walking in."
    ),
}


def generate(base_url, text, seed):
    body = json.dumps({"text": text, "format": "wav", "seed": seed}).encode()
    request = urllib.request.Request(base_url.rstrip("/") + "/v1/tts", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=110) as response:
        return response.read()


if __name__ == "__main__":
    base_url = sys.argv[1]
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "voice-samples")
    output.mkdir(parents=True, exist_ok=True)
    for seed, (name, text) in enumerate(CASES.items(), start=1):
        started = time.perf_counter()
        try:
            audio = generate(base_url, text, seed)
        except Exception as error:  # Report every case; one failure should not hide the rest.
            print(f"{name}: FAILED after {time.perf_counter() - started:.1f}s: {error}", flush=True)
            continue
        (output / f"{name}.wav").write_bytes(audio)
        seconds = (len(audio) - 44) / (44100 * 2)
        print(f"{name}: {seconds:.1f}s of audio in {time.perf_counter() - started:.1f}s", flush=True)
