const TOOLS = {
  audio: {
    button: "Generate Podcast",
    description:
      "Creates a Host / Expert / Student conversation about your document and turns it into an MP3.",
    hint: "This takes 1–3 minutes depending on document length.",
    steps: [
      "Extracting text…",
      "Generating podcast script…",
      "Synthesizing voices… (this takes a while)",
      "Merging audio…",
    ],
  },
  chapters: {
    button: "Create Chapters",
    description:
      "Splits long text into chapters with titles, summaries and key points so it is easier to understand.",
    hint: "Usually takes a few seconds; long documents can take up to a minute.",
    steps: ["Extracting text…", "Finding the structure…", "Writing summaries…"],
  },
};

const $ = (id) => document.getElementById(id);

const form = $("input-form");
const fileInput = $("file-input");
const dropZone = $("drop-zone");
const fileNameEl = $("file-name");
const textInput = $("text-input");
const chapterOptions = $("chapter-options");
const generateBtn = $("generate-btn");
const errorMsg = $("error-msg");
const stepLabel = $("step-label");
const transcriptEl = $("transcript");
const toggleBtn = $("toggle-transcript");

let tool = "audio";
let source = "file";
let lastChapters = null;

// ---------- State helpers ----------

function showState(name) {
  document.querySelectorAll(".state").forEach((s) => s.classList.remove("active"));
  $(`state-${name}`).classList.add("active");
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.classList.remove("hidden");
}

function updateGenerateButton() {
  const ready = source === "file" ? fileInput.files.length > 0 : textInput.value.trim().length > 0;
  generateBtn.disabled = !ready;
}

function selectTool(name) {
  tool = name;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tool === name));
  $("tool-description").textContent = TOOLS[name].description;
  generateBtn.textContent = TOOLS[name].button;
  chapterOptions.classList.toggle("hidden", name !== "chapters");
  errorMsg.classList.add("hidden");
  showState("idle");
}

function selectSource(name) {
  source = name;
  document.querySelectorAll(".seg").forEach((s) => s.classList.toggle("active", s.dataset.source === name));
  dropZone.classList.toggle("hidden", name !== "file");
  textInput.classList.toggle("hidden", name !== "text");
  updateGenerateButton();
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => selectTool(t.dataset.tool)));
document.querySelectorAll(".seg").forEach((s) => s.addEventListener("click", () => selectSource(s.dataset.source)));
textInput.addEventListener("input", updateGenerateButton);

// ---------- File input ----------

function setFile(file) {
  if (!file) return;
  fileNameEl.textContent = file.name;
  updateGenerateButton();
}

fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) {
    fileInput.files = e.dataTransfer.files;
    setFile(e.dataTransfer.files[0]);
  }
});
dropZone.addEventListener("click", (e) => {
  if (e.target.tagName !== "LABEL") fileInput.click();
});

// ---------- Progress ----------

let stepInterval = null;

function startProgress(steps) {
  let idx = 0;
  stepLabel.textContent = steps[0];
  stepInterval = setInterval(() => {
    idx = Math.min(idx + 1, steps.length - 1);
    stepLabel.textContent = steps[idx];
  }, 9000);
}

function stopProgress() {
  clearInterval(stepInterval);
  stepInterval = null;
}

// ---------- API ----------

async function postForm(url, formData) {
  const resp = await fetch(url, { method: "POST", body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(detail || `Server error ${resp.status}`);
  }
  return data;
}

function buildInputForm() {
  const fd = new FormData();
  if (source === "file") fd.append("file", fileInput.files[0]);
  else fd.append("text", textInput.value);
  return fd;
}

// ---------- Audio result ----------

function renderTranscript(script) {
  transcriptEl.innerHTML = "";
  script.forEach(({ narrator, text }) => {
    const div = document.createElement("div");
    div.className = `line ${narrator.toLowerCase()}`;
    const tag = document.createElement("span");
    tag.className = "narrator-tag";
    tag.textContent = narrator;
    const p = document.createElement("p");
    p.className = "line-text";
    p.textContent = text;
    div.append(tag, p);
    transcriptEl.appendChild(div);
  });
}

function showAudioResult(data) {
  $("audio-player").src = data.audio_url;
  const link = $("download-link");
  link.href = data.audio_url;
  link.download = data.audio_url.split("/").pop();
  renderTranscript(data.script);
  showState("audio");
}

toggleBtn.addEventListener("click", () => {
  const hidden = transcriptEl.classList.toggle("hidden");
  toggleBtn.textContent = hidden ? "Show" : "Hide";
});

// ---------- Chapters result ----------

function showChaptersResult(data) {
  lastChapters = data;
  $("doc-title").textContent = data.title;
  $("doc-stats").textContent =
    `${data.chapters.length} chapters · ${data.total_words.toLocaleString()} words · ` +
    `~${data.reading_minutes} min read · ${data.mode === "ai" ? "AI" : "simple"} split`;

  const warning = $("chapters-warning");
  warning.textContent = data.warning || "";
  warning.classList.toggle("hidden", !data.warning);

  const toc = $("toc");
  const list = $("chapter-list");
  const template = $("chapter-template");
  toc.innerHTML = "";
  list.innerHTML = "";

  data.chapters.forEach((ch) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `#chapter-${ch.index}`;
    a.textContent = ch.title;
    li.appendChild(a);
    toc.appendChild(li);

    const node = template.content.firstElementChild.cloneNode(true);
    node.id = `chapter-${ch.index}`;
    node.querySelector(".chapter-num").textContent = ch.index;
    node.querySelector(".chapter-title").textContent = ch.title;
    node.querySelector(".chapter-time").textContent = `${ch.reading_minutes} min`;
    node.querySelector(".chapter-summary").textContent = ch.summary;

    const points = node.querySelector(".key-points");
    ch.key_points.forEach((kp) => {
      const item = document.createElement("li");
      item.textContent = kp;
      points.appendChild(item);
    });
    points.classList.toggle("hidden", ch.key_points.length === 0);

    const textEl = node.querySelector(".chapter-text");
    ch.text.split(/\n\s*\n/).forEach((para) => {
      const p = document.createElement("p");
      p.textContent = para;
      textEl.appendChild(p);
    });

    const audioBtn = node.querySelector(".chapter-audio-btn");
    audioBtn.addEventListener("click", () => createChapterAudio(ch, node, audioBtn));
    list.appendChild(node);
  });

  showState("chapters");
}

async function createChapterAudio(chapter, node, button) {
  const status = node.querySelector(".chapter-status");
  const player = node.querySelector(".chapter-player");
  button.disabled = true;
  status.classList.remove("error");
  status.textContent = "Generating podcast… (1–3 min)";

  const fd = new FormData();
  fd.append("text", `${chapter.title}\n\n${chapter.text}`);
  try {
    const data = await postForm("/api/audio", fd);
    player.src = data.audio_url;
    player.classList.remove("hidden");
    status.textContent = "";
    button.textContent = "🎧 Regenerate audio";
  } catch (err) {
    status.textContent = err.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
  }
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "chapters";
}

$("export-json").addEventListener("click", () => {
  if (!lastChapters) return;
  download(`${slug(lastChapters.title)}.json`, JSON.stringify(lastChapters, null, 2), "application/json");
});

$("export-md").addEventListener("click", async () => {
  if (!lastChapters) return;
  const resp = await fetch("/api/chapters/markdown", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lastChapters),
  });
  download(`${slug(lastChapters.title)}.md`, await resp.text(), "text/markdown");
});

// ---------- Submit / reset ----------

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (generateBtn.disabled) return;

  errorMsg.classList.add("hidden");
  $("loading-hint").textContent = TOOLS[tool].hint;
  showState("loading");
  startProgress(TOOLS[tool].steps);

  const fd = buildInputForm();
  try {
    if (tool === "audio") {
      showAudioResult(await postForm("/api/audio", fd));
    } else {
      fd.append("mode", $("mode-select").value);
      fd.append("max_chapters", $("max-chapters").value || "12");
      showChaptersResult(await postForm("/api/chapters", fd));
    }
  } catch (err) {
    showError(err.message);
    showState("idle");
  } finally {
    stopProgress();
  }
});

document.querySelectorAll(".reset-btn").forEach((btn) =>
  btn.addEventListener("click", () => {
    $("audio-player").src = "";
    transcriptEl.innerHTML = "";
    transcriptEl.classList.add("hidden");
    toggleBtn.textContent = "Show";
    lastChapters = null;
    showState("idle");
    window.scrollTo({ top: 0 });
  })
);

// ---------- Init ----------

selectTool("audio");

fetch("/api/health")
  .then((r) => r.json())
  .then(({ features }) => {
    if (!features.chapters_ai) {
      const mode = $("mode-select");
      mode.value = "simple";
      mode.querySelector('option[value="ai"]').disabled = true;
    }
  })
  .catch(() => {});
