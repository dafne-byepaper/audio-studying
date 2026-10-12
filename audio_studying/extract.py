from pathlib import Path

import fitz  # PyMuPDF
from fastapi import HTTPException

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from an uploaded PDF, TXT or Markdown file."""
    ext = Path(filename or "").suffix.lower()
    if ext == ".pdf":
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read this PDF file.")
        text = "\n".join(page.get_text() for page in doc)
        if len(doc) > 1 and len(text.strip()) < 100:
            raise HTTPException(
                status_code=400,
                detail="This PDF appears to be scanned (image-only). Text extraction is not supported.",
            )
    elif ext in SUPPORTED_EXTENSIONS:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext or 'unknown'}. Upload a .pdf, .txt or .md file.",
        )

    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text could be extracted from this file.")
    return text
