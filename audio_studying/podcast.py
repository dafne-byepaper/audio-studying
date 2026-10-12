"""Turn text into a multi-voice educational podcast (Gemini script + ElevenLabs TTS)."""

import io
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import requests
from fastapi import HTTPException
from pydub import AudioSegment

from . import config, llm


def generate_script(text: str) -> list[dict]:
    narrators = ", ".join(config.VOICE_MAP)
    prompt = (
        "You are a podcast scriptwriter. Output ONLY valid JSON — no markdown, no explanation.\n\n"
        'Return a JSON array where each element has exactly two keys: "narrator" and "text".\n'
        f"Use exactly these narrator names: {narrators}.\n"
        "- Host: introduces topics, guides the conversation, asks bridging questions.\n"
        "- Expert: explains concepts accurately and in depth.\n"
        "- Student: asks questions a confused learner would ask.\n\n"
        "Rules:\n"
        "- 15 to 25 exchanges total.\n"
        '- Each "text" value must be 1–3 sentences maximum.\n'
        "- Make it engaging and educational.\n"
        "- The conversation should cover the main ideas of the document.\n"
        "- Write the dialogue in the same language as the document.\n\n"
        f"Document content:\n{text[: config.MAX_AUDIO_TEXT_CHARS]}"
    )
    script = llm.generate_json(prompt)
    if isinstance(script, dict):
        script = next((v for v in script.values() if isinstance(v, list)), [])

    validated = []
    for item in script if isinstance(script, list) else []:
        if not isinstance(item, dict) or "narrator" not in item or "text" not in item:
            continue
        narrator = item["narrator"] if item["narrator"] in config.VOICE_MAP else "Host"
        validated.append({"narrator": narrator, "text": str(item["text"])})

    if not validated:
        raise HTTPException(
            status_code=502, detail="Script generation failed: no valid dialogue lines produced."
        )
    return validated[: config.MAX_SCRIPT_LINES]


def synthesize_line(text: str, voice_id: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": config.ELEVEN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": text[:2400],
        "model_id": config.ELEVEN_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach ElevenLabs: {exc}")

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="ElevenLabs API key is invalid.")
    if resp.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail="ElevenLabs rate limit reached. You may have exceeded your monthly character quota.",
        )
    if resp.status_code == 422:
        raise HTTPException(
            status_code=422,
            detail=f"ElevenLabs rejected the text (too long or invalid): {resp.text}",
        )
    if not resp.ok:
        raise HTTPException(
            status_code=502, detail=f"ElevenLabs error {resp.status_code}: {resp.text}"
        )
    return resp.content


def merge_audio(segments: list[bytes]) -> bytes:
    silence = AudioSegment.silent(duration=config.SILENCE_MS)
    combined = None
    for seg_bytes in segments:
        seg = AudioSegment.from_file(io.BytesIO(seg_bytes), format="mp3")
        combined = seg if combined is None else combined + silence + seg

    buf = io.BytesIO()
    combined.export(buf, format="mp3")
    return buf.getvalue()


def create_podcast(text: str) -> dict:
    """Generate a podcast for ``text``; returns the audio URL and the script."""
    config.require_audio_stack()
    script = generate_script(text)

    with ThreadPoolExecutor(max_workers=max(1, config.TTS_CONCURRENCY)) as pool:
        segments = list(
            pool.map(lambda line: synthesize_line(line["text"], config.VOICE_MAP[line["narrator"]]), script)
        )

    filename = f"podcast_{uuid4().hex[:8]}.mp3"
    (config.OUTPUT_DIR / filename).write_bytes(merge_audio(segments))
    return {"audio_url": f"/output/{filename}", "script": script}


def cleanup_old_outputs() -> None:
    cutoff = time.time() - config.OUTPUT_TTL_SECONDS
    for f in config.OUTPUT_DIR.glob("*.mp3"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
