import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT_DIR / "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ElevenLabs voices per narrator. Override with ELEVEN_VOICE_HOST, etc.
VOICE_MAP = {
    "Host": os.getenv("ELEVEN_VOICE_HOST", "EXAVITQu4vr4xnSDxMaL"),
    "Expert": os.getenv("ELEVEN_VOICE_EXPERT", "pNInz6obpgDQGcFmaJgB"),
    "Student": os.getenv("ELEVEN_VOICE_STUDENT", "21m00Tcm4TlvDq8ikWAM"),
}
ELEVEN_MODEL = os.getenv("ELEVEN_MODEL", "eleven_multilingual_v2")
TTS_CONCURRENCY = int(os.getenv("TTS_CONCURRENCY", "2"))

SILENCE_MS = 400
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_AUDIO_TEXT_CHARS = int(os.getenv("MAX_AUDIO_TEXT_CHARS", "12000"))
MAX_CHAPTER_TEXT_CHARS = int(os.getenv("MAX_CHAPTER_TEXT_CHARS", "300000"))
MAX_SCRIPT_LINES = 30
OUTPUT_TTL_SECONDS = int(os.getenv("OUTPUT_TTL_SECONDS", "3600"))


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def require_gemini() -> None:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured on the server. Add it to .env.",
        )


def require_audio_stack() -> None:
    require_gemini()
    if not ELEVEN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ELEVEN_API_KEY is not configured on the server. Add it to .env.",
        )
    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="ffmpeg is not installed on the server (e.g. `brew install ffmpeg`).",
        )
