"""Split a long text into study-sized chapters.

Two strategies:

- ``simple``: no API key needed. Uses headings found in the text (Markdown
  ``#``, "Chapter 3", "2.1 Title", ALL CAPS lines). If there are none, groups
  paragraphs into evenly sized chunks.
- ``ai``: Gemini reads the numbered paragraphs and decides where each chapter
  starts, then writes a title, summary and key points for it. Gemini only
  returns paragraph indexes and the text is cut locally, so the chapter text is
  always the original wording.
"""

import re

from . import llm

WORDS_PER_MINUTE = 200
TARGET_CHAPTER_WORDS = 800
MIN_INTRO_WORDS = 40

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_KEYWORD_HEADING = re.compile(
    r"^(chapter|part|section|unit|lesson|module|cap[ií]tulo|parte|secci[oó]n|tema|unidad)"
    r"\s+([0-9]+|[ivxlcdm]+|[a-z]+)\b",
    re.IGNORECASE,
)
_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")
_SENTENCE_END = re.compile(r"[.!?:;\"”’)\]]$")


def count_words(text: str) -> int:
    return len(text.split())


def reading_minutes(words: int) -> int:
    return max(1, round(words / WORDS_PER_MINUTE))


def heading_level(paragraph: str) -> int | None:
    """Return a heading level (1 = top) if the paragraph looks like a heading."""
    if "\n" in paragraph or len(paragraph) > 120:
        return None
    md = _MD_HEADING.match(paragraph)
    if md:
        return len(md.group(1))
    if _KEYWORD_HEADING.match(paragraph):
        return 1
    numbered = _NUMBERED_HEADING.match(paragraph)
    if numbered and len(paragraph) <= 80 and not paragraph.endswith((".", ",", ";")):
        return numbered.group(1).count(".") + 1
    letters = [c for c in paragraph if c.isalpha()]
    if (
        len(letters) >= 4
        and len(paragraph) <= 70
        and paragraph.upper() == paragraph
        and not paragraph.endswith((".", ","))
    ):
        return 1
    return None


def heading_text(paragraph: str) -> str:
    md = _MD_HEADING.match(paragraph)
    title = md.group(2) if md else paragraph
    return title.strip().strip(":").strip()


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs, rebuilding them from lines for PDF-style text."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) >= 3 or len(text) < 2000:
        return blocks

    # Few blank lines (typical for PDF extraction): rebuild paragraphs from
    # lines, ending a paragraph on sentence punctuation or a heading-like line.
    paragraphs: list[str] = []
    current: list[str] = []

    def flush():
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
        elif heading_level(line) is not None:
            flush()
            paragraphs.append(line)
        else:
            current.append(line)
            if _SENTENCE_END.search(line) and count_words(" ".join(current)) >= 40:
                flush()
    flush()
    return paragraphs


def _make_chapter(index: int, title: str, paragraphs: list[str], summary: str = "",
                  key_points: list[str] | None = None) -> dict:
    body = "\n\n".join(paragraphs).strip()
    words = count_words(body)
    return {
        "index": index,
        "title": title,
        "summary": summary or _first_sentences(body),
        "key_points": key_points or [],
        "text": body,
        "word_count": words,
        "reading_minutes": reading_minutes(words),
    }


def _first_sentences(text: str, max_chars: int = 220) -> str:
    flat = " ".join(text.split())
    if len(flat) <= max_chars:
        return flat
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) > max_chars:
            break
        summary = f"{summary} {sentence}".strip()
    return summary or flat[:max_chars].rsplit(" ", 1)[0] + "…"


def _snippet_title(text: str, words: int = 6) -> str:
    parts = text.split()
    snippet = " ".join(parts[:words]).strip(" ,;:.")
    return snippet + ("…" if len(parts) > words else "")


def _result(title: str, mode: str, chapters: list[dict]) -> dict:
    total = sum(c["word_count"] for c in chapters)
    return {
        "title": title,
        "mode": mode,
        "total_words": total,
        "reading_minutes": reading_minutes(total),
        "chapters": chapters,
    }


def _clamp_max(max_chapters: int) -> int:
    return max(1, min(int(max_chapters), 50))


# --------------------------------------------------------------------------- #
# Simple (offline) strategy
# --------------------------------------------------------------------------- #

def _pick_heading_indexes(paragraphs: list[str], max_chapters: int) -> list[int]:
    levels = {i: heading_level(p) for i, p in enumerate(paragraphs)}
    levels = {i: lvl for i, lvl in levels.items() if lvl is not None}
    if not levels:
        return []
    # Use the shallowest heading level that yields at least two chapters.
    for depth in sorted(set(levels.values())):
        idxs = [i for i, lvl in levels.items() if lvl <= depth]
        if len(idxs) >= 2:
            return idxs if len(idxs) <= max_chapters else []
    return []


def _chunk_evenly(paragraphs: list[str], max_chapters: int) -> list[list[str]]:
    total = sum(count_words(p) for p in paragraphs)
    n_chunks = max(1, min(max_chapters, round(total / TARGET_CHAPTER_WORDS)))
    target = total / n_chunks
    chunks: list[list[str]] = [[]]
    running = 0
    for p in paragraphs:
        if running >= target * len(chunks) and len(chunks) < n_chunks and chunks[-1]:
            chunks.append([])
        chunks[-1].append(p)
        running += count_words(p)
    return chunks


def split_simple(text: str, max_chapters: int = 12, fallback_title: str = "") -> dict:
    max_chapters = _clamp_max(max_chapters)
    paragraphs = split_paragraphs(text)
    doc_title = fallback_title or "Untitled document"
    if not paragraphs:
        return _result(doc_title, "simple", [])

    if heading_level(paragraphs[0]) == 1 and _MD_HEADING.match(paragraphs[0]):
        # A leading "# Title" names the whole document, not just chapter 1.
        others = [p for p in paragraphs[1:] if _MD_HEADING.match(p) and heading_level(p) == 1]
        if not others:
            doc_title = heading_text(paragraphs[0])
            paragraphs = paragraphs[1:]

    chapters: list[dict] = []
    starts = _pick_heading_indexes(paragraphs, max_chapters)
    if starts:
        intro = paragraphs[: starts[0]]
        if count_words(" ".join(intro)) >= MIN_INTRO_WORDS:
            chapters.append(_make_chapter(1, "Introduction", intro))
            intro = []
        bounds = starts + [len(paragraphs)]
        for n, (start, end) in enumerate(zip(bounds, bounds[1:])):
            body = paragraphs[start + 1 : end]
            if n == 0:
                body = intro + body
            if not body:
                continue
            chapters.append(
                _make_chapter(len(chapters) + 1, heading_text(paragraphs[start]), body)
            )

    if not chapters:
        for chunk in _chunk_evenly(paragraphs, max_chapters):
            title = f"Part {len(chapters) + 1}: {_snippet_title(chunk[0])}"
            chapters.append(_make_chapter(len(chapters) + 1, title, chunk))

    return _result(doc_title, "simple", chapters)


# --------------------------------------------------------------------------- #
# AI strategy
# --------------------------------------------------------------------------- #

def _build_prompt(paragraphs: list[str], max_chapters: int) -> str:
    numbered = "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs))
    return (
        "You split study material into chapters so it is easier to understand.\n"
        "The document below is divided into numbered paragraphs like [0], [1], ...\n\n"
        "Group consecutive paragraphs into coherent chapters, each covering one idea or topic. "
        f"Use between 1 and {max_chapters} chapters; short documents need fewer. "
        "Prefer existing headings as boundaries when they exist.\n\n"
        "Output ONLY JSON with this shape:\n"
        '{"title": "document title", "chapters": [\n'
        '  {"start_paragraph": 0, "title": "short descriptive title",\n'
        '   "summary": "2-3 sentence plain-language summary",\n'
        '   "key_points": ["3 to 5 short takeaways"]}\n'
        "]}\n\n"
        "Rules:\n"
        "- The first chapter must start at paragraph 0.\n"
        "- start_paragraph values must be strictly increasing.\n"
        "- Write titles, summaries and key points in the same language as the document.\n\n"
        f"Document:\n{numbered}"
    )


def _parse_ai_chapters(data, n_paragraphs: int) -> tuple[str, list[dict]]:
    if isinstance(data, list):
        data = {"chapters": data}
    if not isinstance(data, dict):
        return "", []
    title = str(data.get("title") or "").strip()

    seen: set[int] = set()
    items = []
    for item in data.get("chapters") or []:
        if not isinstance(item, dict):
            continue
        try:
            start = int(item.get("start_paragraph"))
        except (TypeError, ValueError):
            continue
        if not 0 <= start < n_paragraphs or start in seen:
            continue
        seen.add(start)
        key_points = item.get("key_points") or []
        items.append(
            {
                "start": start,
                "title": str(item.get("title") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "key_points": [str(k).strip() for k in key_points if str(k).strip()]
                if isinstance(key_points, list)
                else [],
            }
        )
    items.sort(key=lambda x: x["start"])
    if items:
        items[0]["start"] = 0
    return title, items


def split_ai(text: str, max_chapters: int = 12, fallback_title: str = "") -> dict:
    max_chapters = _clamp_max(max_chapters)
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return _result(fallback_title or "Untitled document", "ai", [])

    data = llm.generate_json(_build_prompt(paragraphs, max_chapters))
    title, items = _parse_ai_chapters(data, len(paragraphs))
    if not items:
        result = split_simple(text, max_chapters, fallback_title)
        result["mode"] = "simple"
        result["warning"] = "The AI response was unusable, so the simple splitter was used."
        return result

    items = items[:max_chapters]
    bounds = [i["start"] for i in items] + [len(paragraphs)]
    chapters = []
    for n, item in enumerate(items):
        body = paragraphs[bounds[n] : bounds[n + 1]]
        chapters.append(
            _make_chapter(
                n + 1,
                item["title"] or f"Chapter {n + 1}",
                body,
                summary=item["summary"],
                key_points=item["key_points"],
            )
        )
    return _result(title or fallback_title or "Untitled document", "ai", chapters)


def split_into_chapters(text: str, mode: str = "ai", max_chapters: int = 12,
                        fallback_title: str = "") -> dict:
    if mode == "simple":
        return split_simple(text, max_chapters, fallback_title)
    return split_ai(text, max_chapters, fallback_title)


def to_markdown(result: dict) -> str:
    """Render a chapters result as a Markdown study guide."""
    lines = [f"# {result['title']}", ""]
    lines.append(
        f"_{len(result['chapters'])} chapters · {result['total_words']} words · "
        f"~{result['reading_minutes']} min read_"
    )
    lines.append("")
    lines.append("## Contents")
    lines.append("")
    for c in result["chapters"]:
        lines.append(f"{c['index']}. {c['title']}")
    for c in result["chapters"]:
        lines += ["", f"## {c['index']}. {c['title']}", ""]
        if c["summary"]:
            lines += [f"> {c['summary']}", ""]
        if c["key_points"]:
            lines += ["**Key points**", ""]
            lines += [f"- {k}" for k in c["key_points"]]
            lines.append("")
        lines.append(c["text"])
    return "\n".join(lines).rstrip() + "\n"
