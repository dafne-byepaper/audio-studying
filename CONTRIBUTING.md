# Contributing to Audio Studying

Thanks for your interest in improving Audio Studying. Bug reports, feature ideas, documentation fixes and code contributions are all welcome.

## Getting started

### Prerequisites

- Python 3.11 or newer
- [ffmpeg](https://ffmpeg.org/) (only needed to work on audio features)

### Development setup

1. Fork the repository and clone your fork:

```bash
   git clone https://github.com/<your-username>/audio-studying.git
   cd audio-studying
```

2. Create a virtual environment and install the development dependencies:

```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
```

3. Copy the example environment file. API keys are optional for development; features that need a missing key return a clear error, and `simple` chapters always work.

```bash
   cp .env.example .env
```

4. Start the development server:

```bash
   uvicorn app:app --reload
```

   The app runs at <http://localhost:8000> and the interactive API docs at <http://localhost:8000/docs>.

## Running tests

```bash
pytest
```

The test suite mocks Gemini and ElevenLabs, so it needs no API keys or network access.

Please add tests for any new behavior. Changes to the chapter splitter in `audio_studying/chapters.py` should always include tests, since it is the most sensitive part of the codebase: chapter text must stay identical to the original document.

## Guidelines

- **Frontend:** keep it dependency-free (plain HTML, CSS and JavaScript, with no build step).
- **Configuration:** read new settings from environment variables in `audio_studying/config.py`, and document them in both the README and `.env.example`.
- **Secrets:** never commit API keys or `.env` files.
- **Scope:** keep pull requests small and focused on a single change. For larger changes, open an issue first so we can agree on the approach before you invest time in it.

## Submitting a pull request

1. Create a branch from `main` with a descriptive name, such as `feature/epub-input` or `fix/empty-pdf-error`.
2. Make your changes and make sure `pytest` passes.
3. Update the README if your change affects usage, configuration or the API.
4. Open a pull request that explains what changed and why, and link any related issue.

## Reporting bugs

When opening an issue, please include:

- What you expected to happen and what happened instead
- Steps to reproduce the problem
- The input type you used (PDF, TXT, Markdown or pasted text)
- Your Python version and operating system
- Relevant error messages or logs, with any API keys removed

## Where we'd love help

- Additional text-to-speech providers, such as OpenAI or local models like Piper and Kokoro
- Additional LLM providers for script writing and chapter generation
- OCR support for scanned PDFs
- EPUB and DOCX input
- Real progress streaming to replace the current simulated progress steps

If you want to work on one of these, comment on the related issue or open a new one so others know it is in progress.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
