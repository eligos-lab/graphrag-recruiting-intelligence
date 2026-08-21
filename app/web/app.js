const api = "/api/v1";
const by = (id) => document.getElementById(id);
let searchStarted;
let progressTimer;

const escapeHtml = (value) => {
  const element = document.createElement("div");
  element.textContent = value || "";
  return element.innerHTML;
};

function setLoading(loading) {
  clearInterval(progressTimer);
  by("p").style.display = loading ? "block" : "none";
  if (!loading) return;
  searchStarted = Date.now();
  progressTimer = setInterval(() => {
    const seconds = Math.floor((Date.now() - searchStarted) / 1000);
    by("time").textContent = `${seconds} сек`;
    by("bar").style.width = `${Math.min(92, 10 + seconds * 3)}%`;
    by("phase").textContent = seconds < 7 ? "Разбираю запрос" : seconds < 17 ? "Ищу по навыкам и смыслу" : "Ранжирую кандидатов";
    by("eta").textContent = seconds < 12 ? "Обычно ещё 10–25 секунд" : "Локальная модель ещё работает";
  }, 300);
}

function formatExperience(value) {
  if (value == null) return "";
  const years = Number(value);
  const displayed = years.toLocaleString("ru-RU", { maximumFractionDigits: 1 });
  if (!Number.isInteger(years)) return `${displayed} года опыта`;
  const lastTwo = years % 100;
  const lastOne = years % 10;
  const unit = lastTwo >= 11 && lastTwo <= 14 ? "лет" : lastOne === 1 ? "год" : lastOne >= 2 && lastOne <= 4 ? "года" : "лет";
  return `${displayed} ${unit} опыта`;
}

function renderCandidate(candidate) {
  const stack = [...new Set([...(candidate.skills || []), ...(candidate.technologies || [])])].slice(0, 5);
  const experience = formatExperience(candidate.years_experience);
  const meta = [candidate.location, experience].filter(Boolean).map(escapeHtml).join(" · ");
  const tags = stack.length
    ? `<div class="candidate-tags">${stack.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`
    : "";
  return `<article class="candidate">
    <div class="top"><span class="candidate-name">${escapeHtml(candidate.full_name)}</span><span class="score">${Math.round(candidate.score * 100)}%</span></div>
    <div class="candidate-title">${escapeHtml(candidate.current_title || "Специализация не указана")}</div>
    ${meta ? `<div class="candidate-meta">${meta}</div>` : ""}
    ${tags}
    <div class="actions"><a href="${api}/candidates/${candidate.candidate_id}/resume.pdf">PDF</a><a href="${api}/candidates/${candidate.candidate_id}/resume.docx">Word</a></div>
  </article>`;
}

by("f").onsubmit = async (event) => {
  event.preventDefault();
  setLoading(true);
  try {
    const response = await fetch(`${api}/search`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: by("q").value, limit: 20, generate_answer: false }) });
    const data = await response.json();
    const candidates = [...(data.candidates || [])].sort((left, right) => right.score - left.score);
    by("count").textContent = `${candidates.length} кандидатов`;
    by("r").innerHTML = candidates.map(renderCandidate).join("");
  } finally {
    setLoading(false);
  }
};

by("file").onchange = (event) => { by("fl").textContent = event.target.files[0]?.name || ""; };
by("uf").onsubmit = async (event) => {
  event.preventDefault();
  const file = by("file").files[0];
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(api + (file.name.endsWith(".zip") ? "/ingestion/jobs/upload-archive" : "/ingestion/jobs/upload"), { method: "POST", body: formData });
  const data = await response.json();
  by("us").textContent = data.detail ? `Ошибка: ${data.detail}` : "Файл принят в обработку";
  by("uf").reset();
  by("fl").textContent = "";
};
by("demo").onclick = async () => {
  const response = await fetch(`${api}/ingestion/jobs/demo`, { method: "POST" });
  by("ds").textContent = response.ok ? "Демо поставлено в очередь" : "Ошибка";
};
