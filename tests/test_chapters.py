from audio_studying import chapters


def words(n: int, word: str = "lorem") -> str:
    return " ".join([word] * n) + "."


def test_split_paragraphs_on_blank_lines():
    text = "One.\n\nTwo.\n\n\nThree."
    assert chapters.split_paragraphs(text) == ["One.", "Two.", "Three."]


def test_split_paragraphs_rebuilds_pdf_lines():
    # Long text without blank lines, wrapped at fixed width like PDF output.
    sentence = "This is a fairly long sentence that wraps across lines in a PDF."
    lines = []
    for _ in range(40):
        lines += ["This is a fairly long sentence that wraps", "across lines in a PDF."]
    lines.insert(20, "CHAPTER 2")
    paragraphs = chapters.split_paragraphs("\n".join(lines))
    assert "CHAPTER 2" in paragraphs
    assert len(paragraphs) > 3
    assert sentence in paragraphs[0]


def test_heading_detection():
    assert chapters.heading_level("# Title") == 1
    assert chapters.heading_level("### Deep") == 3
    assert chapters.heading_level("Chapter 4") == 1
    assert chapters.heading_level("Capítulo 2: Células") == 1
    assert chapters.heading_level("2.1 Photosynthesis") == 2
    assert chapters.heading_level("INTRODUCTION") == 1
    assert chapters.heading_level("This is a normal sentence.") is None
    assert chapters.heading_level("3 apples were eaten by the student yesterday.") is None


def test_simple_uses_markdown_headings():
    text = (
        "# Biology Notes\n\n"
        "## Cells\n\n" + words(100) + "\n\n"
        "## Energy\n\n" + words(120) + "\n\n"
        "## Genetics\n\n" + words(80)
    )
    result = chapters.split_simple(text)
    assert result["title"] == "Biology Notes"
    assert result["mode"] == "simple"
    assert [c["title"] for c in result["chapters"]] == ["Cells", "Energy", "Genetics"]
    assert result["chapters"][1]["word_count"] == 120
    assert [c["index"] for c in result["chapters"]] == [1, 2, 3]


def test_simple_keeps_substantial_intro():
    text = words(60) + "\n\nChapter 1\n\n" + words(50) + "\n\nChapter 2\n\n" + words(50)
    titles = [c["title"] for c in chapters.split_simple(text)["chapters"]]
    assert titles == ["Introduction", "Chapter 1", "Chapter 2"]


def test_simple_chunks_text_without_headings():
    paragraphs = [words(200, f"w{i}") for i in range(20)]  # 4000 words
    result = chapters.split_simple("\n\n".join(paragraphs), max_chapters=12, fallback_title="notes")
    assert result["title"] == "notes"
    assert len(result["chapters"]) == 5
    assert result["chapters"][0]["title"].startswith("Part 1:")
    assert sum(c["word_count"] for c in result["chapters"]) == result["total_words"] == 4000


def test_simple_respects_max_chapters():
    paragraphs = [words(400) for _ in range(20)]
    result = chapters.split_simple("\n\n".join(paragraphs), max_chapters=3)
    assert len(result["chapters"]) == 3


def test_simple_preserves_all_text():
    paragraphs = [f"Paragraph number {i}. " + words(90) for i in range(15)]
    result = chapters.split_simple("\n\n".join(paragraphs))
    rebuilt = "\n\n".join(c["text"] for c in result["chapters"])
    assert rebuilt == "\n\n".join(paragraphs)


def test_ai_split_cuts_original_text(monkeypatch):
    paragraphs = [f"Paragraph {i} about topic {i // 2}." for i in range(6)]
    fake = {
        "title": "Topics",
        "chapters": [
            {"start_paragraph": 4, "title": "Third", "summary": "s3", "key_points": ["c"]},
            {"start_paragraph": 1, "title": "First", "summary": "s1", "key_points": ["a", "b"]},
            {"start_paragraph": 2, "title": "Second", "summary": "s2"},
            {"start_paragraph": 2, "title": "Duplicate"},
            {"start_paragraph": 99, "title": "Out of range"},
        ],
    }
    monkeypatch.setattr(chapters.llm, "generate_json", lambda prompt: fake)

    result = chapters.split_ai("\n\n".join(paragraphs))
    assert result["mode"] == "ai"
    assert result["title"] == "Topics"
    assert [c["title"] for c in result["chapters"]] == ["First", "Second", "Third"]
    # First chapter is forced to start at paragraph 0 so no text is lost.
    assert result["chapters"][0]["text"] == "\n\n".join(paragraphs[0:2])
    assert result["chapters"][2]["text"] == "\n\n".join(paragraphs[4:])
    assert result["chapters"][0]["key_points"] == ["a", "b"]


def test_ai_split_falls_back_to_simple(monkeypatch):
    monkeypatch.setattr(chapters.llm, "generate_json", lambda prompt: {"nope": True})
    result = chapters.split_ai("# A\n\n" + words(50) + "\n\n# B\n\n" + words(50))
    assert result["mode"] == "simple"
    assert "warning" in result
    assert [c["title"] for c in result["chapters"]] == ["A", "B"]


def test_to_markdown():
    result = chapters.split_simple("## One\n\n" + words(10) + "\n\n## Two\n\n" + words(10), fallback_title="Doc")
    md = chapters.to_markdown(result)
    assert md.startswith("# Doc\n")
    assert "## 1. One" in md and "## 2. Two" in md
