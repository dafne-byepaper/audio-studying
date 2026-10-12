# Audio Studying

An open-source service that helps you study long documents in two ways:

1. **🎧 Audio**: turns a document into a multi-voice educational podcast. Gemini writes a
   Host / Expert / Student conversation, ElevenLabs voices each line, and everything is merged
   into one MP3.
2. **📚 Chapters**: breaks long text into chapters with a title, a short summary and key
   points, so it is easier to understand piece by piece. You can then make a podcast for
   any single chapter with one click.

Input can be a **PDF, TXT or Markdown file**, or **pasted text**.

## How chapters work

| Method | Needs | What you get |
| --- | --- | --- |
| `ai` (default) | `GEMINI_API_KEY` | Gemini picks where each topic starts, then writes the title, summary and 3–5 key points for each chapter. |
| `simple` | nothing | Uses the document's headings (`# Markdown`, `Chapter 3`, `2.1 Title`, `ALL CAPS`). If there are no headings, it splits the text into even parts of about 800 words. |

In both methods the chapter text is the **original text, never rewritten**. The AI only
returns the index of the paragraph where each chapter starts, and the server cuts the
document at those points. This means no content is lost or invented.

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) (only for audio)
- A [Google Gemini API key](https://aistudio.google.com/apikey) (for audio and AI chapters)
- An [ElevenLabs API key](https://elevenlabs.io/) (only for audio)

The app starts without any keys. Features that need a missing key return a clear error, and
`simple` chapters always work.

## Quick start

```bash
brew install ffmpeg            # or: apt install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # then add your API keys
uvicorn app:app --reload
```

Open <http://localhost:8000>.

### Docker

```bash
docker build -t audio-studying .
docker run -p 8000:8000 --env-file .env audio-studying
```

## API

Interactive docs are at <http://localhost:8000/docs>. Every endpoint accepts either a
`file` upload or a `text` form field.

### `POST /api/chapters`

| Field | Default | Description |
| --- | --- | --- |
| `file` / `text` | — | The document to split |
| `mode` | `ai` | `ai` or `simple` |
| `max_chapters` | `12` | Upper limit (1–50) |

```bash
curl -X POST localhost:8000/api/chapters -F file=@notes.pdf -F mode=ai
```

```json
{
  "title": "Photosynthesis and Cellular Respiration",
  "mode": "ai",
  "total_words": 112,
  "reading_minutes": 1,
  "chapters": [
    {
      "index": 1,
      "title": "Photosynthesis: Capturing Light Energy",
      "summary": "Photosynthesis is the process plants use to…",
      "key_points": ["Photosynthesis converts light energy into chemical energy.", "…"],
      "text": "Photosynthesis is the process plants use…",
      "word_count": 65,
      "reading_minutes": 1
    }
  ]
}
```

### `POST /api/chapters/markdown`

Send the JSON returned by `/api/chapters` and get back a Markdown study guide with a table of
contents.

### `POST /api/audio`

```bash
curl -X POST localhost:8000/api/audio -F text="Your chapter text…"
```

Returns `{"audio_url": "/output/podcast_ab12cd34.mp3", "script": [{"narrator": "Host", "text": "…"}]}`.

### `GET /api/health`

Shows which features are available on this server.

## Configuration

All settings come from environment variables (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Script writing and AI chapters |
| `ELEVEN_API_KEY` | — | Text-to-speech |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `ELEVEN_MODEL` | `eleven_multilingual_v2` | ElevenLabs model |
| `ELEVEN_VOICE_HOST` / `_EXPERT` / `_STUDENT` | built-in voices | Voice IDs for each narrator |
| `TTS_CONCURRENCY` | `2` | Lines synthesized in parallel (respect your ElevenLabs plan limit) |
| `MAX_AUDIO_TEXT_CHARS` | `12000` | Characters of input used to write a podcast script |
| `MAX_CHAPTER_TEXT_CHARS` | `300000` | Largest text accepted for chapters |
| `OUTPUT_TTL_SECONDS` | `3600` | Generated MP3s are deleted after this many seconds |

## Project layout

```
audio_studying/
  main.py       FastAPI app and routes
  chapters.py   Chapter splitting (simple + AI) and Markdown export
  podcast.py    Script generation, text-to-speech, audio merging
  extract.py    PDF / TXT / Markdown text extraction
  llm.py        Gemini JSON helper
  config.py     Environment-based settings
static/         Web UI (plain HTML/CSS/JS, no build step)
tests/          pytest suite (no API keys needed)
```

## Limits

- Max upload size: 10 MB.
- Scanned (image-only) PDFs are not supported. The text must be extractable.
- Podcast scripts are capped at 30 dialogue lines.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
