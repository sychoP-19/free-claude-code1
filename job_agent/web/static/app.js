/* JobAgent Pro — SPA frontend logic */

/** state — single source of truth */
const state = { jobs: [], settings: {}, keywords: [], resume: {}, toastTimer: null };

/* ====== API CLIENT ====== */
const api = {
  async request(path, opts) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000);
    try {
      const r = await fetch(path, { ...opts, signal: ctrl.signal });
      clearTimeout(timer);
      return await r.json();
    } catch (e) {
      clearTimeout(timer);
      if (e.name === "AbortError") throw new Error("Request timed out");
      throw e;
    }
  },
  get(path) { return this.request(path); },
  post(path, body) {
    return this.request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
};

/* ====== TOAST ====== */
function toast(msg, type) {
  if (state.toastTimer) clearTimeout(state.toastTimer);
  const c = document.getElementById("toastContainer");
  c.innerHTML = `<div class="toast toast-${type || "info"}">${msg}</div>`;
  state.toastTimer = setTimeout(() => { c.innerHTML = ""; }, 3500);
}

/* ====== HASH ROUTING ====== */
function navigate(route) {
  document.querySelectorAll(".page-section").forEach((s) => s.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
  const page = document.getElementById("page-" + route);
  const nav = document.querySelector(`[data-route="${route}"]`);
  if (page) page.classList.add("active");
  if (nav) nav.classList.add("active");
  const sidebar = document.getElementById("sidebar");
  if (sidebar) sidebar.classList.remove("open");
}

/* ====== LOAD ALL ====== */
async function loadAll() {
  // Show skeletons first
  const skeletons = document.querySelectorAll(".skeleton-card");
  skeletons.forEach(s => s.style.display = "block");

  try {
    const [settings, jobs, resume] = await Promise.all([
      api.get("/api/settings"),
      api.get("/api/jobs"),
      api.get("/api/resume"),
    ]);
    state.settings = settings;
    state.jobs = Array.isArray(jobs) ? jobs : [];
    state.resume = resume || {};
    state.keywords = (settings.keywords || []).map((k) => k.toLowerCase());

    // Hide skeletons and render
    skeletons.forEach(s => s.style.display = "none");
    renderDashboard();
    renderDashboardNotes();
    renderKeywords();
    renderResume();
    renderApproved();
    renderSettings();
    updateApprovedBadge();
  } catch (err) {
    // Hide skeletons on error too
    skeletons.forEach(s => s.style.display = "none");
    console.error("Failed to load data:", err);
  }
}

/* ====== DASHBOARD ====== */
function renderDashboard() {
  const jobs = state.jobs;
  const total = jobs.length;
  const pending = jobs.filter((j) => !j.status || j.status === "new").length;
  const approved = jobs.filter((j) => j.status === "approved").length;
  const scores = jobs.map((j) => j.match_score).filter((s) => s != null);
  const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  animateValue("statTotal", total);
  animateValue("statNew", pending);
  animateValue("statApproved", approved);
  document.getElementById("statAvgScore").textContent = avg + "%";
  document.getElementById("statusText").textContent = total ? `${total} jobs loaded` : "Ready";
}

function animateValue(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  let current = 0;
  const step = Math.max(1, Math.floor(target / 30));
  const iv = setInterval(() => {
    current += step;
    if (current >= target) { current = target; clearInterval(iv); }
    el.textContent = current;
  }, 40);
}

async function renderDashboardNotes() {
  try {
    const data = await api.get("/api/notes");
    const notes = data.text || "";
    const lines = notes.split("\n").filter(Boolean);
    const recent = lines.slice(-5).reverse();
    const container = document.getElementById("dashboardNotes");
    if (!recent.length) {
      container.innerHTML =
        '<div class="empty-state"><div class="empty-icon">&#9998;</div><h3>No notes yet</h3><p>Add notes to keep track of your job search progress.</p></div>';
      return;
    }
    container.innerHTML = recent
      .map((n) => `<div class="note-item">${escapeHtml(n)}</div>`)
      .join("");
  } catch {
    /* silent */
  }
}

/* ====== SEARCH ====== */
async function runSearch(save) {
  const kwInput = document.getElementById("searchKeywords");
  const keywords = kwInput.value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!keywords.length && !state.keywords.length) {
    toast("Enter at least one keyword", "error");
    return;
  }
  const endpoint = save ? "/api/search" : "/api/search/preview";
  const statusEl = document.getElementById("searchStatus");
  const statusText = document.getElementById("searchStatusText");
  statusEl.style.display = "flex";
  statusText.textContent = "Searching...";
  document.getElementById("searchResultsContainer").style.display = "none";
  document.getElementById("searchEmpty").style.display = "none";
  try {
    const data = await api.post(endpoint, {
      keywords: keywords.length ? keywords : state.keywords,
      locations: state.settings.locations || {},
    });
    statusEl.style.display = "none";
    if (data.jobs && data.jobs.length) {
      renderSearchResults(data.jobs);
      if (save) {
        await loadAll();
        toast(`Found ${data.total} jobs (${data.new_count} new)`, "success");
      } else {
        toast(`Preview: ${data.jobs.length} results`, "info");
      }
    } else {
      document.getElementById("searchEmpty").style.display = "block";
      toast("No results found", "info");
    }
  } catch {
    statusEl.style.display = "none";
    toast("Search failed", "error");
  }
}

function formatDate(d) {
  if (!d) return "-";
  const s = String(d).slice(0, 10);
  if (!s) return "-";
  return s;
}

function renderSearchResults(jobs) {
  const tbody = document.getElementById("searchResultsBody");
  tbody.innerHTML = jobs
    .map((j) => {
      const score = j.match_score || 0;
      const scoreClass = score >= 70 ? "high" : score >= 40 ? "medium" : "low";
      const status = j.status || "new";
      const badgeClass =
        status === "approved" ? "badge-approved" :
        status === "rejected" ? "badge-rejected" :
        "badge-new";
      const actionBtn =
        status === "approved"
          ? `<button class="btn btn-xs btn-glass" onclick="updateJobStatus('${escapeHtml(j.url)}','rejected')">Reject</button>`
          : `<button class="btn btn-xs btn-primary" onclick="updateJobStatus('${escapeHtml(j.url)}','approved')">Approve</button>`;
      return `<tr>
        <td><span class="badge ${badgeClass}">${status}</span></td>
        <td><a href="${escapeHtml(j.url)}" target="_blank" class="job-title-link">${escapeHtml(j.title || "Untitled")}</a></td>
        <td>${escapeHtml(j.company || "-")}</td>
        <td>${escapeHtml(j.location || "-")}</td>
        <td>${escapeHtml(j.source || "-")}</td>
        <td>${formatDate(j.date_found)}</td>
        <td><div class="score-bar"><span class="score-fill ${scoreClass}" style="width:${score}%"></span><span class="score-label">${score}%</span></div></td>
        <td>${actionBtn}</td>
      </tr>`;
    })
    .join("");
  document.getElementById("searchResultsContainer").style.display = "block";
  document.getElementById("searchEmpty").style.display = "none";
}

async function updateJobStatus(url, status) {
  await api.post("/api/jobs", { url, status });
  const data = await api.get("/api/jobs");
  state.jobs = Array.isArray(data) ? data : [];
  renderDashboard();
  renderApproved();
  updateApprovedBadge();
  const hash = location.hash.replace("#", "");
  if (hash === "search") {
    const existing = document.getElementById("searchResultsContainer");
    if (existing.style.display !== "none") {
      const rows = document.querySelectorAll("#searchResultsBody tr");
      rows.forEach((row) => {
        const link = row.querySelector(".job-title-link");
        if (link && link.href === url) {
          const badge = row.querySelector(".badge");
          const action = row.querySelector("td:last-child");
          if (badge) { badge.className = `badge badge-${status}`; badge.textContent = status; }
          if (action) {
            action.innerHTML =
              status === "approved"
                ? `<button class="btn btn-xs btn-glass" onclick="updateJobStatus('${escapeHtml(url)}','rejected')">Reject</button>`
                : `<button class="btn btn-xs btn-primary" onclick="updateJobStatus('${escapeHtml(url)}','approved')">Approve</button>`;
          }
        }
      });
    }
  }
  toast(`Job ${status}`, "success");
}

function updateApprovedBadge() {
  const count = state.jobs.filter((j) => j.status === "approved").length;
  const el = document.getElementById("approvedCount");
  if (el) el.textContent = count;
}

/* ====== KEYWORDS ====== */
function renderKeywords() {
  const container = document.getElementById("keywordsList");
  const count = document.getElementById("keywordCount");
  if (!state.keywords.length) {
    container.innerHTML =
      '<div class="empty-state"><div class="empty-icon">#</div><h3>No keywords</h3><p>Add keywords or import them from your resume.</p></div>';
    if (count) count.textContent = "0";
    return;
  }
  if (count) count.textContent = state.keywords.length;
  container.innerHTML = state.keywords
    .map(
      (kw) =>
        `<span class="chip" onclick="removeKeyword('${escapeHtml(kw)}')">${escapeHtml(kw)} <span class="chip-remove">&times;</span></span>`
    )
    .join("");
}

async function addKeyword() {
  const input = document.getElementById("newKeyword");
  const kw = input.value.trim().toLowerCase();
  if (!kw) return;
  if (!state.keywords.includes(kw)) {
    state.keywords.push(kw);
    state.settings.keywords = [...state.keywords];
    await api.post("/api/settings", state.settings);
    renderKeywords();
  }
  input.value = "";
}

async function removeKeyword(kw) {
  state.keywords = state.keywords.filter((k) => k !== kw);
  state.settings.keywords = [...state.keywords];
  await api.post("/api/settings", state.settings);
  renderKeywords();
}

async function importKeywords() {
  const data = await api.post("/api/resume/keywords");
  if (data.imported && data.imported.length) {
    data.imported.forEach((kw) => { if (!state.keywords.includes(kw)) state.keywords.push(kw); });
    state.settings.keywords = [...state.keywords];
    await api.post("/api/settings", state.settings);
    renderKeywords();
    toast(`Imported ${data.imported.length} keywords`, "success");
  } else {
    toast("No new keywords to import", "info");
  }
}

/* ====== RESUME ====== */
function renderResume() {
  const text = state.resume.text || "No resume loaded.";
  document.getElementById("resumeText").textContent = text;
  const skills = state.resume.keywords || [];
  const skillsContainer = document.getElementById("resumeKeywords");
  if (skills.length) {
    skillsContainer.innerHTML = skills
      .map((s) => `<span class="chip">${escapeHtml(s)}</span>`)
      .join("");
  } else {
    skillsContainer.innerHTML =
      '<div class="empty-state" style="padding:12px"><p>No skills extracted.</p></div>';
  }
  const langs = state.resume.languages || {};
  const langContainer = document.getElementById("resumeLanguages");
  langContainer.innerHTML = Object.keys(langs).length
    ? Object.entries(langs)
        .map(([lang, level]) => `<span class="badge badge-language">${escapeHtml(lang)}: ${escapeHtml(level)}</span>`)
        .join("")
    : '<span class="chip">No language data</span>';
}

/* ====== APPROVED ====== */
function renderApproved() {
  const container = document.getElementById("approvedContainer");
  const approved = state.jobs.filter((j) => j.status === "approved");
  const rejected = state.jobs.filter((j) => j.status === "rejected");

  // Approved section
  let approvedHTML = '<div class="section-filter"><h2>Approved (' + approved.length + ')</h2></div><div class="approved-grid">';
  if (!approved.length) {
    approvedHTML +=
      '<div class="empty-state"><div class="empty-icon">&#10003;</div><h3>No approved jobs</h3><p>Search for jobs and approve matching ones from the results.</p></div>';
  } else {
    approvedHTML += approved
      .map((j) => {
        const score = j.match_score || 0;
        const scoreClass = score >= 70 ? "high" : score >= 40 ? "medium" : "low";
        return `<div class="approved-card glass-card">
          <div class="approved-header">
            <a href="${escapeHtml(j.url)}" target="_blank" class="job-title-link">${escapeHtml(j.title || "Untitled")}</a>
            <span class="badge badge-approved">Approved</span>
          </div>
          <div class="approved-meta">${escapeHtml(j.company || "-")} &middot; ${escapeHtml(j.location || "-")}</div>
          <div class="approved-footer">
            <div class="score-bar"><span class="score-fill ${scoreClass}" style="width:${score}%"></span><span class="score-label">${score}%</span></div>
            <div style="display:flex;gap:6px">
              <button class="btn btn-xs btn-glass" onclick="window.open('${escapeHtml(j.url)}','_blank')">Open</button>
              <button class="btn btn-xs btn-glass" onclick="updateJobStatus('${escapeHtml(j.url)}','rejected')">Reject</button>
            </div>
          </div>
        </div>`;
      })
      .join("");
  }
  approvedHTML += '</div>';

  // Rejected section
  let rejectedHTML = '<div class="section-filter"><h2>Rejected (' + rejected.length + ')</h2></div><div class="rejected-grid">';
  if (!rejected.length) {
    rejectedHTML += '<div class="empty-state"><p>No rejected jobs.</p></div>';
  } else {
    rejectedHTML += rejected
      .map((j) => {
        const score = j.match_score || 0;
        const scoreClass = score >= 70 ? "high" : score >= 40 ? "medium" : "low";
        return `<div class="rejected-card glass-card">
          <div class="rejected-header">
            <a href="${escapeHtml(j.url)}" target="_blank" class="job-title-link">${escapeHtml(j.title || "Untitled")}</a>
            <span class="badge badge-rejected">Rejected</span>
          </div>
          <div class="rejected-meta">${escapeHtml(j.company || "-")} &middot; ${escapeHtml(j.location || "-")}</div>
          <div class="rejected-footer">
            <div class="score-bar"><span class="score-fill ${scoreClass}" style="width:${score}%"></span><span class="score-label">${score}%</span></div>
            <div style="display:flex;gap:6px">
              <button class="btn btn-xs btn-glass" onclick="window.open('${escapeHtml(j.url)}','_blank')">Open</button>
              <button class="btn btn-xs btn-primary" onclick="updateJobStatus('${escapeHtml(j.url)}','approved')">Re-approve</button>
            </div>
          </div>
        </div>`;
      })
      .join("");
  }
  rejectedHTML += '</div>';

  container.innerHTML = approvedHTML + rejectedHTML;
}

/* ====== SETTINGS ====== */
function renderSettings() {
  const s = state.settings;
  const gmailUser = document.getElementById("setGmailUser");
  const gmailPass = document.getElementById("setGmailPass");
  if (gmailUser) gmailUser.value = s.gmail_user || "";
  if (gmailPass) gmailPass.value = s.gmail_pass || "";
  const scheduleTime = document.getElementById("setScheduleTime");
  if (scheduleTime) scheduleTime.value = s.schedule_time || "09:00";
  const threshold = document.getElementById("setMatchThreshold");
  const label = document.getElementById("matchThresholdLabel");
  if (threshold) { threshold.value = s.match_threshold || 50; }
  if (label) label.textContent = (s.match_threshold || 50) + "%";
  // location toggles
  const locContainer = document.getElementById("locationToggles");
  const locations = s.locations || {};
  if (locContainer) {
    locContainer.innerHTML = Object.entries(locations).map(
      ([key, val]) =>
        `<label class="toggle-item ${val ? "active" : ""}"><input type="checkbox" ${val ? "checked" : ""} data-loc="${escapeHtml(key)}"> <span>${escapeHtml(key)}</span></label>`
    ).join("");
    // Add change handlers for locations
    locContainer.querySelectorAll("input[data-loc]").forEach(cb => {
      cb.addEventListener("change", () => {
        const label = cb.closest(".toggle-item");
        if (cb.checked) label.classList.add("active");
        else label.classList.remove("active");
      });
    });
  }
  // language toggles
  const langToggles = document.getElementById("languageToggles");
  const langs = s.languages || {};
  if (langToggles) {
    langToggles.innerHTML = Object.keys(langs).length
      ? Object.entries(langs).map(
          ([key, val]) =>
            `<label class="toggle-item ${val ? "active" : ""}"><input type="checkbox" ${val ? "checked" : ""} data-lang="${escapeHtml(key)}"> <span>${escapeHtml(key)}</span></label>`
        ).join("")
      : '<span style="color:var(--color-text-secondary);font-size:0.85rem">Configure in resume</span>';
    // Add change handlers for languages
    langToggles.querySelectorAll("input[data-lang]").forEach(cb => {
      cb.addEventListener("change", () => {
        const label = cb.closest(".toggle-item");
        if (cb.checked) label.classList.add("active");
        else label.classList.remove("active");
      });
    });
  }
}

async function saveSettings() {
  const s = { ...state.settings };
  s.gmail_user = document.getElementById("setGmailUser")?.value || "";
  s.gmail_pass = document.getElementById("setGmailPass")?.value || "";
  s.schedule_time = document.getElementById("setScheduleTime")?.value || "09:00";
  s.match_threshold = parseInt(document.getElementById("setMatchThreshold")?.value || "50");
  // locations
  const locToggles = document.querySelectorAll("#locationToggles input[data-loc]");
  const locations = {};
  locToggles.forEach((cb) => { locations[cb.dataset.loc] = cb.checked; });
  s.locations = locations;
  // languages
  const langToggles = document.querySelectorAll("#languageToggles input[data-lang]");
  if (langToggles.length) {
    const langs = {};
    langToggles.forEach((cb) => { langs[cb.dataset.lang] = cb.checked; });
    s.languages = langs;
  }
  await api.post("/api/settings", s);
  state.settings = s;
  toast("Settings saved", "success");
}

async function testEmail() {
  const user = document.getElementById("setGmailUser")?.value || "";
  const pwd = document.getElementById("setGmailPass")?.value || "";
  if (!user || !pwd) { toast("Enter email and app password first", "error"); return; }
  const data = await api.post("/api/email/test", { user, pass: pwd });
  toast(data.ok ? "Email sent!" : "Email failed", data.ok ? "success" : "error");
}

/* ====== EXPORT ====== */
function setupExport() {
  document.getElementById("exportPDF")?.addEventListener("click", () => {
    toast("PDF export placeholder — implement with print or a library", "info");
  });
  document.getElementById("exportReport")?.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ jobs: state.jobs, settings: state.settings }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jobagent-report.json";
    a.click();
    URL.revokeObjectURL(url);
    toast("Report downloaded", "success");
  });
  document.getElementById("exportPrint")?.addEventListener("click", () => window.print());
}

/* ====== UTILITY ====== */
function escapeHtml(str) {
  if (str == null) return "";
  const d = document.createElement("div");
  d.appendChild(document.createTextNode(str));
  return d.innerHTML;
}

async function addNote() {
  const input = document.getElementById("noteInput");
  const text = input.value.trim();
  if (!text) return;
  await api.post("/api/notes", { text });
  input.value = "";
  renderDashboardNotes();
  toast("Note added", "success");
}

/* ====== AUTO-REFRESH ====== */
let autoRefreshInterval = null;

function startAutoRefresh() {
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  // Poll every 30 seconds for status updates
  autoRefreshInterval = setInterval(async () => {
    try {
      const jobs = await api.get("/api/jobs");
      state.jobs = Array.isArray(jobs) ? jobs : [];
      updateApprovedBadge();
      // Update status bar
      const total = state.jobs.length;
      const statusText = document.getElementById("statusText");
      if (statusText) {
        statusText.textContent = total ? `${total} jobs loaded` : "Ready";
      }
    } catch (err) {
      // Silent fail for background polling
      console.debug("Auto-refresh poll failed:", err);
    }
  }, 30000); // 30 second interval
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
}

/* ====== INIT ====== */
function init() {
  // navigation
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const route = btn.dataset.route;
      location.hash = route;
      navigate(route);
    });
  });
  // hash change
  window.addEventListener("hashchange", () => {
    const route = location.hash.replace("#", "") || "dashboard";
    navigate(route);
  });
  // mobile sidebar toggle
  const brand = document.querySelector(".statusbar-brand");
  if (brand) {
    brand.addEventListener("click", () => {
      document.getElementById("sidebar")?.classList.toggle("open");
    });
  }
  // search
  document.getElementById("btnSearch")?.addEventListener("click", () => runSearch(true));
  document.getElementById("btnPreview")?.addEventListener("click", () => runSearch(false));
  document.getElementById("searchKeywords")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch(true);
  });
  // notes
  document.getElementById("btnAddNote")?.addEventListener("click", addNote);
  document.getElementById("noteInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addNote();
  });
  // keywords
  document.getElementById("btnAddKeyword")?.addEventListener("click", addKeyword);
  document.getElementById("newKeyword")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addKeyword();
  });
  document.getElementById("btnImportKeywords")?.addEventListener("click", importKeywords);
  // settings
  document.getElementById("btnSaveSettings")?.addEventListener("click", saveSettings);
  document.getElementById("btnTestEmail")?.addEventListener("click", testEmail);
  document.getElementById("setMatchThreshold")?.addEventListener("input", function () {
    document.getElementById("matchThresholdLabel").textContent = this.value + "%";
  });
  // export
  setupExport();
  // start auto-refresh
  startAutoRefresh();
  // load data
  loadAll();
  // initial route
  const route = location.hash.replace("#", "") || "dashboard";
  navigate(route);

  // Stop auto-refresh when page is hidden (saves resources)
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopAutoRefresh();
    else startAutoRefresh();
  });
}

document.addEventListener("DOMContentLoaded", init);