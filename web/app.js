// Maths Shorts Studio — front end
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const BEAT_META = {
  hook: { label: "HOOK", colour: "var(--rose)" },
  setup: { label: "SETUP", colour: "var(--blue)" },
  maths: { label: "THE MATHS", colour: "var(--accent)" },
  payoff: { label: "PAYOFF", colour: "var(--teal)" },
};

const state = { config: null, script: null, job: null, es: null };

const store = {
  get(k, d = null) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* not json */ }
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map(d => d.msg).join("; ");
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function busy(btn, on, label) {
  if (on) {
    btn.dataset.label = btn.innerHTML;
    btn.innerHTML = `<span class="spin"></span>${label}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.label || btn.innerHTML;
    btn.disabled = false;
  }
}

function showError(id, msg) {
  const el = $(id);
  if (!msg) { el.classList.add("hidden"); return; }
  el.textContent = msg;
  el.classList.remove("hidden");
}

// ------------------------------------------------------------- navigation
function showView(name) {
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${name}`));
  $$(".nav-btn[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "library") loadLibrary();
}

function gotoStep(n) {
  $$(".step").forEach(s => s.classList.toggle("active", s.id === `step-${n}`));
  $$(".stepper li").forEach(li => {
    const k = +li.dataset.step;
    li.classList.toggle("active", k === n);
    li.classList.toggle("done", k < n);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ------------------------------------------------------------- config
function fillVoices() {
  const lang = $("#language").value;
  const voices = state.config.voices[lang] || {};
  $("#voice").innerHTML = Object.entries(voices).map(([label, id]) => `<option value="${esc(id)}">${esc(label)}</option>`).join("");
}

function updateKeyUI() {
  const has = state.config.has_key;
  $("#key-banner").classList.toggle("hidden", has || $("#demo").checked);
  $("#key-status").innerHTML = has
    ? `<span style="color:var(--teal)">✓ A key is saved on this computer.</span> Paste a new one to replace it.`
    : `<span style="color:var(--accent)">No key saved yet.</span> Get a free one at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a>.`;
}

async function loadConfig() {
  state.config = await api("/api/config");
  const c = state.config;
  $("#language").innerHTML = c.languages.map(l => `<option>${esc(l)}</option>`).join("");
  fillVoices();
  $("#ideas").innerHTML = c.topic_ideas.map(t => `<button class="chip" type="button">${esc(t)}</button>`).join("");
  $$("#ideas .chip").forEach(b => b.addEventListener("click", () => { $("#topic").value = b.textContent; $("#topic").focus(); }));
  $("#model").value = store.get("model", c.default_model);
  $("#code-model").value = store.get("codeModel", c.default_model);
  $("#latex-status").innerHTML = c.latex
    ? `<span style="color:var(--teal)">✓ Found</span>: formulas render as real maths.`
    : `<span style="color:var(--accent)">Not found</span>: formulas will show as plain text. Install MiKTeX (Windows) or MacTeX (Mac), then restart.`;
  restoreOptions();
  updateKeyUI();
}

// ------------------------------------------------------------- options
const OPTION_IDS = ["language", "seconds", "level", "voice", "quality", "rate", "scene-mode", "attempts", "brand", "review-first"];

function saveOptions() {
  const o = {};
  OPTION_IDS.forEach(id => { const el = $("#" + id); o[id] = el.type === "checkbox" ? el.checked : el.value; });
  store.set("options", o);
  updateOptionsSummary();
}

function restoreOptions() {
  const o = store.get("options", {});
  if (o.language) { $("#language").value = o.language; fillVoices(); }
  OPTION_IDS.forEach(id => {
    if (id === "language" || o[id] === undefined) return;
    const el = $("#" + id);
    if (el.type === "checkbox") el.checked = !!o[id]; else el.value = o[id];
  });
  $("#rate-val").textContent = `${+$("#rate").value > 0 ? "+" : ""}${$("#rate").value}%`;
  updateOptionsSummary();
}

function updateOptionsSummary() {
  const voice = $("#voice").selectedOptions[0];
  $("#options-summary").textContent = `· ${$("#language").value} · ${$("#seconds").value} s · ${voice ? voice.textContent.split(" (")[0] : ""} · ${$("#quality").value === "final" ? "1080p" : "draft"}`;
}

function videoOptions() {
  const demo = $("#demo").checked;
  return {
    demo,
    voice: demo ? "en-IN-NeerjaNeural" : $("#voice").value,
    rate_pct: +$("#rate").value,
    quality: $("#quality").value,
    max_attempts: Math.min(5, Math.max(1, +$("#attempts").value || 3)),
    use_llm_scene: $("#scene-mode").value === "llm",
    brand: $("#brand").value.trim() || "MATHS IN THE WILD",
    model: $("#model").value.trim(),
    code_model: $("#code-model").value.trim(),
  };
}

// ------------------------------------------------------------- step 1
function checkReady() {
  const demo = $("#demo").checked;
  showError("#script-error", null);
  if (!demo && !$("#topic").value.trim()) { showError("#script-error", "Type a topic first, e.g. Eigenvalues, or tap one of the ideas."); return false; }
  if (!demo && !state.config.has_key) { showError("#script-error", "Add your Gemini key in Settings (⚙), or switch on Demo mode."); return false; }
  return true;
}

function go() {
  if (!checkReady()) return;
  if ($("#review-first").checked) writeScript(); else makeAuto();
}

async function makeAuto() {
  const btn = $("#btn-go");
  busy(btn, true, "Starting…");
  try {
    const { job_id } = await api("/api/auto", {
      method: "POST",
      body: { topic: $("#topic").value.trim(), language: $("#language").value, seconds: +$("#seconds").value,
              level: $("#level").value, ...videoOptions() },
    });
    resetRender(true);
    gotoStep(3);
    $("#stepper-review").classList.remove("done");
    follow(job_id);
  } catch (e) {
    showError("#script-error", e.message);
  } finally {
    busy(btn, false);
  }
}

async function writeScript() {
  const demo = $("#demo").checked;
  const topic = $("#topic").value.trim();
  const btn = $("#btn-go");
  busy(btn, true, demo ? "Loading demo…" : "Researching… (30–60 s)");
  try {
    const script = await api("/api/script", {
      method: "POST",
      body: { topic, demo, language: $("#language").value, seconds: +$("#seconds").value,
              level: $("#level").value, model: $("#model").value.trim() },
    });
    state.script = script;
    store.set("draft", { script, voice: $("#voice").value, language: $("#language").value });
    renderReview();
    gotoStep(2);
  } catch (e) {
    showError("#script-error", e.message);
  } finally {
    busy(btn, false);
  }
}

// ------------------------------------------------------------- step 2
function wps() {
  return (state.config.words_per_sec || {})[state.script.language] || 2.5;
}

function texPreview(el, tex) {
  if (!tex.trim()) { el.innerHTML = ""; return; }
  if (window.katex) {
    try { katex.render(tex, el, { throwOnError: false, displayMode: false }); return; } catch { /* fall through */ }
  }
  el.textContent = tex;
}

function updateEstimates() {
  let total = 0;
  $$(".beat").forEach(card => {
    const words = $(".narr", card).value.trim().split(/\s+/).filter(Boolean).length;
    const secs = words / wps();
    total += secs;
    $(".secs", card).textContent = `≈ ${secs.toFixed(0)} s spoken`;
  });
  const target = state.script.seconds || 60;
  const el = $("#total-est");
  el.textContent = `Estimated length ≈ ${total.toFixed(0)} s (target ${target} s)`;
  el.style.color = total > target * 1.25 ? "var(--rose)" : "";
}

function renderReview() {
  const s = state.script;
  $("#title").value = s.title || "";
  $("#description").value = s.description || "";
  $("#beats").innerHTML = s.beats.map((b, i) => {
    const m = BEAT_META[b.name] || { label: b.name.toUpperCase(), colour: "var(--accent)" };
    return `
    <div class="card beat" style="--c:${m.colour}" data-i="${i}">
      <div class="beat-head"><span class="tag">${m.label}</span><span class="secs"></span></div>
      <label class="field"><span>Narration (what the voice says)</span>
        <textarea class="narr" rows="4">${esc(b.narration)}</textarea></label>
      <div class="two">
        <label class="field"><span>On-screen headline</span><input type="text" class="key" value="${esc(b.key_text)}"></label>
        <label class="field"><span>Formula (LaTeX)</span><input type="text" class="tex" value="${esc(b.formula)}" spellcheck="false"></label>
      </div>
      <div class="tex-preview"></div>
      <label class="field"><span>Animation idea</span><textarea class="anim" rows="2">${esc(b.on_screen)}</textarea></label>
    </div>`;
  }).join("");
  $$(".beat").forEach(card => {
    const prev = $(".tex-preview", card);
    const tex = $(".tex", card);
    texPreview(prev, tex.value);
    tex.addEventListener("input", () => { texPreview(prev, tex.value); saveDraft(); });
    $(".narr", card).addEventListener("input", () => { updateEstimates(); saveDraft(); });
    $$(".key, .anim", card).forEach(el => el.addEventListener("input", saveDraft));
  });
  updateEstimates();

  const v = s.numbers_to_verify || [];
  $("#verify-card").classList.toggle("hidden", !v.length);
  $("#verify-list").innerHTML = v.map(n => `<li>${esc(n)}</li>`).join("");
  const src = s.sources || [];
  $("#sources-card").classList.toggle("hidden", !src.length);
  $("#source-count").textContent = src.length ? `(${src.length})` : "";
  $("#source-list").innerHTML = src.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title || x.url)}</a></li>`).join("");
  $("#notes-card").classList.toggle("hidden", !s.research_notes);
  $("#notes").textContent = s.research_notes || "";
}

function collectScript() {
  const s = structuredClone(state.script);
  s.title = $("#title").value.trim() || s.title;
  s.description = $("#description").value;
  $$(".beat").forEach(card => {
    const b = s.beats[+card.dataset.i];
    b.narration = $(".narr", card).value.trim();
    b.key_text = $(".key", card).value.trim();
    b.formula = $(".tex", card).value.trim();
    b.on_screen = $(".anim", card).value.trim();
  });
  return s;
}

function saveDraft() {
  if (!state.script) return;
  store.set("draft", { script: collectScript(), voice: $("#voice").value, language: $("#language").value });
}

// ------------------------------------------------------------- step 3
function setPhase(name, status, sub) {
  const li = $(`.phases li[data-phase="${name}"]`);
  if (!li) return;
  li.classList.remove("active", "done");
  if (status) li.classList.add(status);
  if (sub && name === "anim") $("#anim-sub").textContent = sub;
}

function resetRender(auto = false) {
  $$(".phases li").forEach(li => li.classList.remove("active", "done"));
  $$(".phases .auto-only").forEach(li => li.classList.toggle("hidden", !auto));
  $("#anim-sub").textContent = "Writing the Manim scene";
  $("#check-sub").textContent = "Recomputing every number";
  $("#log").textContent = "";
  $("#result").classList.add("hidden");
  $("#result-notes").innerHTML = "";
  $("#checked").classList.add("hidden");
  $("#checked").open = false;
  showError("#render-error", null);
  $("#player").classList.add("hidden");
  $("#player").removeAttribute("src");
  $("#placeholder").classList.remove("hidden");
  $(".wave").classList.remove("hidden");
  $(".downloads").classList.remove("hidden");
  $("#placeholder-text").textContent = "Starting…";
  $("#render-title").textContent = "Making your short";
  const topic = $("#demo").checked ? "Demo: UPI pay-later" : (auto ? $("#topic").value.trim() : (state.script && state.script.title) || "");
  $("#render-topic").textContent = topic ? `Topic: ${topic}` : "";
}

function onLog(line) {
  const log = $("#log");
  log.textContent += line + "\n";
  log.scrollTop = log.scrollHeight;
  const ph = $("#placeholder-text");
  if (line.startsWith("Demo mode")) { ["research", "script", "check"].forEach(p => setPhase(p, "done")); }
  else if (line.startsWith("Researching")) { setPhase("research", "active"); ph.textContent = "Searching the web…"; }
  else if (line.startsWith("Research done")) setPhase("research", "done");
  else if (line.startsWith("Writing the four-beat script")) { setPhase("script", "active"); ph.textContent = "Writing the script…"; }
  else if (line.startsWith("Script ready")) setPhase("script", "done");
  else if (line.startsWith("Fact-checking")) { setPhase("check", "active"); ph.textContent = "Checking the maths…"; }
  else if (/correction\(s\) made|No errors found|Fact-check skipped|keeping the original/.test(line)) {
    setPhase("check", "done");
    $("#check-sub").textContent = line.trim();
  }
  else if (line.startsWith("Recording narration")) {
    ["research", "script", "check"].forEach(p => { const li = $(`.phases li[data-phase="${p}"]`); if (!li.classList.contains("hidden")) setPhase(p, "done"); });
    setPhase("voice", "active"); ph.textContent = "Recording the narration…";
  }
  else if (line.startsWith("Narration:")) setPhase("voice", "done");
  else if (line.startsWith("Gemini is writing")) {
    const m = line.match(/attempt (\d+)\/(\d+)/);
    setPhase("anim", "active", m ? `Gemini is writing the scene (attempt ${m[1]} of ${m[2]})` : "Gemini is writing the scene");
    ph.textContent = "Designing the animation…";
  }
  else if (line.includes("Rendering")) { setPhase("anim", "active"); ph.textContent = "Rendering frames…"; }
  else if (line.startsWith("Using the template")) { setPhase("anim", "active", "Using the template animation"); ph.textContent = "Rendering the template…"; }
  else if (line.includes("Rendered.")) setPhase("anim", "done");
  else if (line.startsWith("Mixing")) { setPhase("anim", "done"); setPhase("mix", "active"); ph.textContent = "Mixing voice and picture…"; }
}

function renderChecked(r) {
  const s = r.script || {};
  const parts = [];
  if (r.issues && r.issues.length) parts.push(`<h4>Fixed by the fact-check</h4><ul>${r.issues.map(i => `<li>${esc(i)}</li>`).join("")}</ul>`);
  else if (s.research_notes) parts.push(`<h4>Fact-check</h4><p class="muted">No errors found.</p>`);
  if (s.numbers_to_verify && s.numbers_to_verify.length) parts.push(`<h4>Numbers and claims in the video</h4><ul>${s.numbers_to_verify.map(n => `<li>${esc(n)}</li>`).join("")}</ul>`);
  if (s.sources && s.sources.length) parts.push(`<h4>Web sources</h4><ul>${s.sources.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title || x.url)}</a></li>`).join("")}</ul>`);
  $("#checked-body").innerHTML = parts.join("");
  $("#checked").classList.toggle("hidden", !parts.length);
}

function fileUrl(name, file, download = false) {
  return `/api/videos/${encodeURIComponent(name)}/files/${file}${download ? "?download=true" : ""}`;
}

function onDone(r) {
  $$(".phases li:not(.hidden)").forEach(li => setPhase(li.dataset.phase, "done"));
  if (r.script) {
    state.script = r.script;
    store.set("draft", { script: r.script, voice: $("#voice").value, language: $("#language").value });
    renderReview();
  }
  renderChecked(r);
  $("#render-title").textContent = r.title || "Your short is ready";
  const player = $("#player");
  player.src = `${fileUrl(r.name, "final.mp4")}?t=${Date.now()}`;
  player.classList.remove("hidden");
  $("#placeholder").classList.add("hidden");
  $("#dl-mp4").href = fileUrl(r.name, "final.mp4", true);
  $("#dl-srt").href = fileUrl(r.name, "captions.srt", true);
  $("#dl-scene").href = fileUrl(r.name, "scene.py", true);
  $("#copy-desc").dataset.text = r.description || "";
  const notes = [`<div class="banner ok">${r.duration.toFixed(0)}-second short saved in <code>outputs/${esc(r.name)}</code>.</div>`];
  if (r.used_fallback) notes.push(`<div class="banner info">Gemini's animation didn't render, so the simple template was used. Try again, choose a Pro model for animation code in Settings, or make the animation ideas simpler.</div>`);
  if (r.overrun > 1) notes.push(`<div class="banner info">The animation runs ${r.overrun.toFixed(1)} s past the narration, so the end is silent.</div>`);
  $("#result-notes").innerHTML = notes.join("");
  $("#result").classList.remove("hidden");
}

function onFailed(msg) {
  $$(".phases li.active").forEach(li => li.classList.remove("active"));
  $("#render-title").textContent = "The video couldn't be made";
  $("#placeholder-text").textContent = "Stopped.";
  $(".wave").classList.add("hidden");
  showError("#render-error", msg);
  $("#result").classList.remove("hidden");
  $(".downloads").classList.add("hidden");
}

async function makeVideo() {
  showError("#video-error", null);
  const script = collectScript();
  if (script.beats.some(b => !b.narration)) { showError("#video-error", "Every beat needs narration."); return; }
  const btn = $("#btn-video");
  busy(btn, true, "Starting…");
  try {
    const { job_id } = await api("/api/videos", { method: "POST", body: { script, ...videoOptions() } });
    resetRender(false);
    gotoStep(3);
    follow(job_id);
  } catch (e) {
    showError("#video-error", e.message);
  } finally {
    busy(btn, false);
  }
}

function follow(jobId) {
  if (state.es) state.es.close();
  const es = new EventSource(`/api/videos/${jobId}/events`);
  state.es = es;
  es.addEventListener("queued", e => {
    const { ahead } = JSON.parse(e.data);
    $("#placeholder-text").textContent = ahead > 0 ? `Waiting: ${ahead} video${ahead > 1 ? "s" : ""} ahead of yours…` : "Starting…";
  });
  es.addEventListener("log", e => onLog(JSON.parse(e.data)));
  es.addEventListener("done", e => { es.close(); onDone(JSON.parse(e.data)); });
  es.addEventListener("failed", e => { es.close(); onFailed(JSON.parse(e.data)); });
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) onFailed("Lost the connection to the studio. Is the server window still open?");
  };
}

// ------------------------------------------------------------- library
async function loadLibrary() {
  const grid = $("#lib-grid");
  try {
    const items = await api("/api/videos");
    $("#lib-empty").classList.toggle("hidden", items.length > 0);
    grid.innerHTML = items.map(j => `
      <div class="lib-card">
        <video src="${fileUrl(j.name, "final.mp4")}#t=6" preload="metadata" controls playsinline></video>
        <div class="meta">
          <b>${esc(j.title)}</b>
          <span class="pill">${esc(j.language)}</span><span class="pill">${Math.round(j.duration)} s</span><span class="pill">${esc(j.quality)}</span>
          <div class="muted small">${esc(j.created)}</div>
          <div class="row gap">
            <a class="btn primary" href="${fileUrl(j.name, "final.mp4", true)}">⬇ MP4</a>
            <a class="btn ghost" href="${fileUrl(j.name, "captions.srt", true)}">SRT</a>
          </div>
        </div>
      </div>`).join("");
  } catch (e) {
    grid.innerHTML = `<div class="banner error">${esc(e.message)}</div>`;
  }
}

// ------------------------------------------------------------- settings
async function saveKey() {
  const key = $("#key-input").value.trim();
  if (!key) return;
  const btn = $("#save-key");
  busy(btn, true, "Saving…");
  try {
    await api("/api/key", { method: "POST", body: { key } });
    state.config.has_key = true;
    $("#key-input").value = "";
    updateKeyUI();
  } catch (e) {
    $("#key-status").innerHTML = `<span style="color:var(--rose)">${esc(e.message)}</span>`;
  } finally {
    busy(btn, false);
  }
}

// ------------------------------------------------------------- wire up
function init() {
  $$(".nav-btn[data-view]").forEach(b => b.addEventListener("click", () => showView(b.dataset.view)));
  const dlg = $("#settings");
  $$("#open-settings, [data-open-settings]").forEach(b => b.addEventListener("click", () => dlg.showModal()));
  $("#save-key").addEventListener("click", saveKey);
  $("#model").addEventListener("change", e => store.set("model", e.target.value.trim()));
  $("#code-model").addEventListener("change", e => store.set("codeModel", e.target.value.trim()));
  $("#language").addEventListener("change", () => { fillVoices(); saveOptions(); });
  $("#demo").addEventListener("change", updateKeyUI);
  $("#btn-go").addEventListener("click", go);
  $("#topic").addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  OPTION_IDS.forEach(id => $("#" + id).addEventListener("change", saveOptions));
  $("#btn-video").addEventListener("click", makeVideo);
  $("#rate").addEventListener("input", e => { $("#rate-val").textContent = `${e.target.value > 0 ? "+" : ""}${e.target.value}%`; });
  $("#title").addEventListener("input", saveDraft);
  $("#description").addEventListener("input", saveDraft);
  $$("[data-goto]").forEach(b => b.addEventListener("click", () => gotoStep(+b.dataset.goto)));
  $("#btn-new").addEventListener("click", () => { $("#topic").value = ""; gotoStep(1); $("#topic").focus(); });
  $$(".stepper li").forEach(li => li.addEventListener("click", () => {
    const n = +li.dataset.step;
    if (n === 1 || (n === 2 && state.script)) gotoStep(n);
  }));
  $("#copy-desc").addEventListener("click", async e => {
    const text = e.target.dataset.text || "";
    try { await navigator.clipboard.writeText(text); e.target.textContent = "Copied ✓"; }
    catch { e.target.textContent = "Copy failed"; }
    setTimeout(() => { e.target.textContent = "Copy description"; }, 1500);
  });

  loadConfig().then(() => {
    const draft = store.get("draft");
    if (draft && draft.script) {
      state.script = draft.script;
      renderReview();
      $(".stepper li[data-step='2']").title = "Your last script is saved here";
    }
  }).catch(e => showError("#script-error", `Can't reach the studio server: ${e.message}`));
}

document.addEventListener("DOMContentLoaded", init);
