from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, chapters, config, podcast
from .extract import extract_text

app = FastAPI(
    title="Audio Studying",
    version=__version__,
    description="Turn documents into educational podcasts and digestible chapters.",
)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=config.OUTPUT_DIR), name="output")


def read_input(file: UploadFile | None, text: str | None) -> tuple[str, str]:
    """Return (text, title) from either an uploaded file or a pasted text field."""
    if file is not None and file.filename:
        contents = file.file.read()
        if len(contents) > config.MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")
        return extract_text(contents, file.filename), Path(file.filename).stem
    if text and text.strip():
        return text.strip(), ""
    raise HTTPException(status_code=400, detail="Provide a file or some text.")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "features": {
            "audio": bool(config.GEMINI_API_KEY and config.ELEVEN_API_KEY and config.ffmpeg_available()),
            "chapters_ai": bool(config.GEMINI_API_KEY),
            "chapters_simple": True,
        },
    }


@app.post("/api/audio")
def create_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
):
    """Create a multi-voice podcast MP3 from a document or pasted text."""
    source, _ = read_input(file, text)
    result = podcast.create_podcast(source)
    background_tasks.add_task(podcast.cleanup_old_outputs)
    return result


@app.post("/api/chapters")
def create_chapters(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    mode: Literal["ai", "simple"] = Form("ai"),
    max_chapters: int = Form(12, ge=1, le=50),
):
    """Split a document or pasted text into chapters with titles and summaries."""
    source, title = read_input(file, text)
    if len(source) > config.MAX_CHAPTER_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Text too long for chapters (max {config.MAX_CHAPTER_TEXT_CHARS:,} characters).",
        )
    return chapters.split_into_chapters(source, mode, max_chapters, fallback_title=title)


class ChaptersResult(BaseModel):
    title: str
    total_words: int
    reading_minutes: int
    chapters: list[dict]


@app.post("/api/chapters/markdown", response_class=PlainTextResponse)
def chapters_markdown(result: ChaptersResult):
    """Render a chapters result (from /api/chapters) as a Markdown study guide."""
    return chapters.to_markdown(result.model_dump())


# Backwards-compatible alias for the original endpoint.
@app.post("/upload", include_in_schema=False)
def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return create_audio(background_tasks, file=file, text=None)
