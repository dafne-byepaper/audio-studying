# Contributing

Thanks for helping improve Audio Studying!

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app:app --reload
```

## Running tests

```bash
pytest
```

The tests mock Gemini and ElevenLabs, so they need no API keys or network access.
Please add tests for new behavior, especially for the chapter splitter in
`audio_studying/chapters.py`.

## Guidelines

- Keep the frontend dependency-free (plain HTML/CSS/JS, no build step).
- Read new settings from environment variables in `audio_studying/config.py` and document them
  in the README and `.env.example`.
- Never commit API keys or `.env` files.
- Keep pull requests focused. For bigger changes, open an issue first so we can agree on
  the approach.

## Ideas we'd love help with

- More TTS providers (OpenAI, local models such as Piper or Kokoro)
- More LLM providers for scripts and chapters
- OCR for scanned PDFs
- EPUB / DOCX input
- Progress streaming instead of the simulated progress steps
