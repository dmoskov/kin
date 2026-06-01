// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

let CURRENT_DOC_ID = null;
let CURRENT_PROPOSED = null;

(function initDocUpload() {
  const btn = document.getElementById("doc-upload-btn");
  const overlay = document.getElementById("doc-upload-overlay");
  const closeBtn = document.getElementById("doc-upload-close");
  const dropZone = document.getElementById("doc-drop-zone");
  const dropContent = document.getElementById("doc-drop-content");
  const fileInput = document.getElementById("doc-file-input");
  const progressEl = document.getElementById("doc-progress");
  const errorBox = document.getElementById("doc-error-box");
  const errorTitle = document.getElementById("doc-error-title");
  const errorDetail = document.getElementById("doc-error-detail");
  const retryBtn = document.getElementById("doc-error-retry");
  const resumeBtn = document.getElementById("doc-chunk-resume");

  if (!btn || !overlay) return;

  const historyEl = document.getElementById("doc-history");
  const historyList = document.getElementById("doc-history-list");

  function openModal() {
    resetDocUI();
    overlay.classList.remove("hidden");
    loadDocHistory();
  }

  function closeModal() {
    overlay.classList.add("hidden");
  }

  function resetDocUI() {
    progressEl.classList.add("hidden");
    errorBox.classList.add("hidden");
    dropZone.style.display = "";
    setStep("doc-step-prepare", "pending", "");
    setStep("doc-step-upload", "pending", "");
    setStep("doc-step-analyze", "pending", "");
    const chunkProgress = document.getElementById("doc-chunk-progress");
    if (chunkProgress) chunkProgress.classList.add("hidden");
    if (resumeBtn) resumeBtn.classList.add("hidden");
  }

  function setStep(id, status, detail) {
    const el = document.getElementById(id);
    if (el) {
      el.dataset.status = status;
      const detailEl = document.getElementById(id + "-detail");
      if (detailEl) detailEl.textContent = detail || "";
    }
  }

  function showError(title, detail) {
    errorBox.classList.remove("hidden");
    errorTitle.textContent = title;
    errorDetail.textContent = detail;
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  btn.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

  // Drop zone interactions
  dropZone.addEventListener("click", (e) => {
    if (e.target !== fileInput && e.target.tagName !== "LABEL") fileInput.click();
  });
  dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) handleDocFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) handleDocFile(fileInput.files[0]);
    fileInput.value = "";
  });

  retryBtn.addEventListener("click", () => {
    resetDocUI();
    dropZone.style.display = "";
  });

  if (resumeBtn) {
    resumeBtn.addEventListener("click", async () => {
      if (!CURRENT_DOC_ID) return;
      resumeBtn.classList.add("hidden");
      errorBox.classList.add("hidden");
      setStep("doc-step-analyze", "active", "Resuming...");
      await runResumeFlow(CURRENT_DOC_ID, "Resumed document");
    });
  }

  let _lastFile = null;

  async function handleDocFile(originalFile) {
    _lastFile = originalFile;

    // Show progress, hide drop zone
    dropZone.style.display = "none";
    progressEl.classList.remove("hidden");
    errorBox.classList.add("hidden");

    // ── Step 1: Prepare ──
    setStep("doc-step-prepare", "active", `${originalFile.name} (${formatSize(originalFile.size)})`);

    let file;
    try {
      file = await resizeImageFile(originalFile);
    } catch (err) {
      setStep("doc-step-prepare", "error", "Failed to process image");
      showError("Could not process file", err.message);
      return;
    }

    const wasResized = file !== originalFile;
    const prepareDetail = wasResized
      ? `${originalFile.name} resized: ${formatSize(originalFile.size)} \u2192 ${formatSize(file.size)}`
      : `${originalFile.name} (${formatSize(file.size)})`;
    setStep("doc-step-prepare", "done", prepareDetail);

    // ── Step 2: Upload ──
    setStep("doc-step-upload", "active", `Sending ${formatSize(file.size)}...`);

    const formData = new FormData();
    formData.append("file", file);

    let uploadResp;
    try {
      uploadResp = await fetch("/api/documents/upload", { method: "POST", body: formData });
    } catch (err) {
      setStep("doc-step-upload", "error", "Connection failed");
      showError("Upload failed", `Could not connect to server: ${err.message}`);
      return;
    }

    const uploadData = await uploadResp.json().catch(() => ({}));
    if (!uploadResp.ok) {
      setStep("doc-step-upload", "error", `HTTP ${uploadResp.status}`);
      const detail = uploadData.code === "too_large"
        ? `File is ${formatSize(file.size)} but the server limit is ${formatSize(50 * 1024 * 1024)}. Try a smaller file or compress it first.`
        : uploadData.code === "invalid_type"
        ? `${uploadData.error}. Supported: JPEG, PNG, WebP, GIF, PDF.`
        : uploadData.error || `Server returned HTTP ${uploadResp.status}`;
      showError("Upload failed", detail);
      return;
    }

    CURRENT_DOC_ID = uploadData.document_id;
    setStep("doc-step-upload", "done", `Uploaded as ${uploadData.file_type}`);

    // ── Step 3: AI Analysis ──
    setStep("doc-step-analyze", "active", "Claude is reading the document...");

    let parseResp;
    try {
      parseResp = await fetch(`/api/documents/${CURRENT_DOC_ID}/parse`, { method: "POST" });
    } catch (err) {
      setStep("doc-step-analyze", "error", "Connection lost");
      showError("AI analysis failed", `Lost connection to server during analysis. This can happen with large files. Error: ${err.message}`);
      return;
    }

    let parseData;
    try {
      parseData = await parseResp.json();
    } catch (err) {
      setStep("doc-step-analyze", "error", "Invalid response");
      showError("AI analysis failed", "The server returned an invalid response. This usually means the request timed out. Try a smaller or clearer image.");
      return;
    }

    if (!parseResp.ok) {
      setStep("doc-step-analyze", "error", `HTTP ${parseResp.status}`);
      const detail = parseData.code === "parse_failed"
        ? `The AI could not extract data from this document. ${parseData.error || ""}`
        : parseData.error || "An unknown error occurred during analysis.";
      showError("AI analysis failed", detail);
      return;
    }

    // All parsing is async — poll for completion
    const total = parseData.total_chunks || 1;
    const chunkProgressEl = document.getElementById("doc-chunk-progress");
    const chunkFill = document.getElementById("doc-chunk-fill");
    const chunkText = document.getElementById("doc-chunk-text");

    if (total > 1 && chunkProgressEl) {
      chunkProgressEl.classList.remove("hidden");
      setStep("doc-step-analyze", "active", `Processing ${total} sections...`);
    }

    const pollResult = await pollParseStatus(CURRENT_DOC_ID, total, chunkFill, chunkText);
    if (!pollResult) {
      // pollParseStatus already showed the error or stalled state (the latter
      // reveals the Resume button) — don't clobber it with a generic error.
      return;
    }

    parseData = pollResult;

    // Success
    const pc = parseData.proposed_changes;
    const peopleCount = (pc?.people || []).length;
    const eventCount = (pc?.events || []).length;
    const unionCount = (pc?.unions || []).length;
    setStep("doc-step-analyze", "done", `Found ${peopleCount} people, ${eventCount} events, ${unionCount} unions`);

    // Brief pause so user can see the success state, then open review
    setTimeout(() => {
      closeModal();
      CURRENT_PROPOSED = pc;
      openReviewModal(pc, originalFile.name);
    }, 800);
  }

  async function pollParseStatus(docId, totalChunks, fillEl, textEl) {
    const POLL_INTERVAL = 2000;
    const MAX_POLLS = 300; // 10 minutes max

    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise(r => setTimeout(r, POLL_INTERVAL));

      let resp;
      try {
        resp = await fetch(`/api/documents/${docId}/parse-status`);
      } catch (_) {
        continue; // retry on network blip
      }

      let data;
      try {
        data = await resp.json();
      } catch (_) {
        continue;
      }

      const total = data.total_chunks || totalChunks;
      const done = data.chunks_done || 0;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      if (fillEl) fillEl.style.width = pct + "%";
      if (textEl) textEl.textContent = `${done} / ${total} sections`;
      setStep("doc-step-analyze", "active", `Processing section ${Math.min(done + 1, total)} of ${total}...`);

      if (data.status === "parsed") {
        if (fillEl) fillEl.style.width = "100%";
        if (textEl) textEl.textContent = `${total} / ${total} sections`;
        return data;
      }

      if (data.status === "error") {
        showError("AI analysis failed", data.error || "An error occurred during analysis.");
        return null;
      }

      if (data.status === "stalled") {
        setStep("doc-step-analyze", "error", `Processing interrupted at ${done}/${total} sections`);
        if (resumeBtn) {
          resumeBtn.textContent = `Resume from section ${done + 1}`;
          resumeBtn.classList.remove("hidden");
        }
        return null;
      }
    }

    showError("AI analysis timed out", "The document is taking too long to process. Please try again with a shorter document.");
    return null;
  }

  // Shared resume sequence: (re)trigger parsing for a document, show chunk
  // progress, poll to completion, then open the review modal. Used by the
  // Resume button and resume-from-history. The caller is responsible for its
  // own preamble (hiding UI, setting the prepare/upload steps). docId should
  // already equal CURRENT_DOC_ID.
  async function runResumeFlow(docId, label) {
    let parseResp;
    try {
      parseResp = await fetch(`/api/documents/${docId}/parse`, { method: "POST" });
    } catch (err) {
      setStep("doc-step-analyze", "error", "Connection lost");
      showError("Resume failed", `Could not connect to server: ${err.message}`);
      return;
    }
    let parseData;
    try {
      parseData = await parseResp.json();
    } catch (_) {
      setStep("doc-step-analyze", "error", "Invalid response");
      showError("Resume failed", "The server returned an invalid response.");
      return;
    }
    if (!parseResp.ok) {
      setStep("doc-step-analyze", "error", `HTTP ${parseResp.status}`);
      showError("Resume failed", parseData.error || "An unknown error occurred.");
      return;
    }

    const total = parseData.total_chunks || 1;
    const chunkProgressEl = document.getElementById("doc-chunk-progress");
    const chunkFill = document.getElementById("doc-chunk-fill");
    const chunkText = document.getElementById("doc-chunk-text");

    if (total > 1 && chunkProgressEl) {
      chunkProgressEl.classList.remove("hidden");
      const done = parseData.chunks_done || 0;
      const pct = Math.round((done / total) * 100);
      if (chunkFill) chunkFill.style.width = pct + "%";
      if (chunkText) chunkText.textContent = `${done} / ${total} sections`;
      setStep("doc-step-analyze", "active", `Resuming from section ${done + 1} of ${total}...`);
    }

    const pollResult = await pollParseStatus(docId, total, chunkFill, chunkText);
    if (!pollResult) return; // pollParseStatus already showed the error/stalled state

    const pc = pollResult.proposed_changes;
    const peopleCount = (pc?.people || []).length;
    const eventCount = (pc?.events || []).length;
    const unionCount = (pc?.unions || []).length;
    setStep("doc-step-analyze", "done", `Found ${peopleCount} people, ${eventCount} events, ${unionCount} unions`);

    setTimeout(() => {
      closeModal();
      CURRENT_PROPOSED = pc;
      openReviewModal(pc, label);
    }, 800);
  }

  // ── Document History ──────────────────────────────────────────────

  function timeAgo(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return "";
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return date.toLocaleDateString();
  }

  async function loadDocHistory() {
    if (!historyEl || !historyList) return;
    let docs;
    try {
      const resp = await fetch("/api/documents");
      if (!resp.ok) { historyEl.classList.add("hidden"); return; }
      docs = await resp.json();
    } catch (_) {
      historyEl.classList.add("hidden");
      return;
    }
    if (!Array.isArray(docs) || docs.length === 0) {
      historyEl.classList.add("hidden");
      return;
    }
    historyEl.classList.remove("hidden");
    historyList.innerHTML = "";
    for (const doc of docs) {
      const row = document.createElement("div");
      row.className = "doc-history-item";

      const name = document.createElement("span");
      name.className = "doc-history-name";
      name.textContent = doc.filename || "Untitled";
      name.title = doc.filename || "";
      row.appendChild(name);

      // Chunk progress for multi-chunk docs
      if (doc.total_chunks > 1 && doc.status !== "uploaded") {
        const meta = document.createElement("span");
        meta.className = "doc-history-meta";
        meta.textContent = `${doc.chunks_done}/${doc.total_chunks}`;
        row.appendChild(meta);
      }

      const badge = document.createElement("span");
      badge.className = "doc-status-badge";
      badge.dataset.status = doc.status;
      badge.textContent = doc.status;
      row.appendChild(badge);

      const ts = document.createElement("span");
      ts.className = "doc-history-meta";
      ts.textContent = timeAgo(doc.uploaded_at);
      row.appendChild(ts);

      // Action buttons based on status
      if (doc.status === "stalled" || doc.status === "error") {
        const actionBtn = document.createElement("button");
        actionBtn.className = "doc-history-action";
        actionBtn.textContent = doc.status === "stalled" ? "Resume" : "Retry";
        actionBtn.addEventListener("click", () => resumeFromHistory(doc));
        row.appendChild(actionBtn);
      } else if (doc.status === "parsed") {
        const viewBtn = document.createElement("button");
        viewBtn.className = "doc-history-action";
        viewBtn.textContent = "Apply";
        viewBtn.addEventListener("click", () => viewResultsFromHistory(doc));
        row.appendChild(viewBtn);
      } else if (doc.status === "applied") {
        const viewBtn = document.createElement("button");
        viewBtn.className = "doc-history-action";
        viewBtn.textContent = "View";
        viewBtn.addEventListener("click", () => viewResultsFromHistory(doc));
        row.appendChild(viewBtn);
      }

      historyList.appendChild(row);
    }
  }

  function resumeFromHistory(doc) {
    CURRENT_DOC_ID = doc.id;
    historyEl.classList.add("hidden");
    dropZone.style.display = "none";
    progressEl.classList.remove("hidden");
    errorBox.classList.add("hidden");
    setStep("doc-step-prepare", "done", doc.filename);
    setStep("doc-step-upload", "done", doc.file_type || "uploaded");
    setStep("doc-step-analyze", "active", "Resuming...");
    runResumeFlow(doc.id, doc.filename || "Resumed document");
  }

  async function viewResultsFromHistory(doc) {
    CURRENT_DOC_ID = doc.id;
    let resp;
    try {
      resp = await fetch(`/api/documents/${doc.id}/parse-status`);
    } catch (_) {
      showToast("Could not load results", "error");
      return;
    }
    let data;
    try {
      data = await resp.json();
    } catch (_) {
      showToast("Invalid response from server", "error");
      return;
    }
    if (data.proposed_changes) {
      closeModal();
      CURRENT_PROPOSED = data.proposed_changes;
      openReviewModal(data.proposed_changes, doc.filename || "Document", doc.status === "applied");
    } else {
      showToast("No parsed results available", "error");
    }
  }
})();

// ═══════════════════════════════════════════════════════════════
// GEDCOM Import
// ═══════════════════════════════════════════════════════════════

(function initGedcomImport() {
  const btn = document.getElementById("gedcom-import-btn");
  const overlay = document.getElementById("gedcom-overlay");
  const closeBtn = document.getElementById("gedcom-close");
  const dropZone = document.getElementById("gedcom-drop-zone");
  const fileInput = document.getElementById("gedcom-file-input");
  const statusEl = document.getElementById("gedcom-status");
  const statusText = document.getElementById("gedcom-status-text");

  if (!btn || !overlay) return;

  function openGedcomModal() { overlay.classList.remove("hidden"); }
  function closeGedcomModal() { overlay.classList.add("hidden"); statusEl?.classList.add("hidden"); }

  btn.addEventListener("click", openGedcomModal);
  closeBtn?.addEventListener("click", closeGedcomModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeGedcomModal(); });

  // Also wire up the onboarding "Import GEDCOM" button
  document.getElementById("onboard-import-gedcom")?.addEventListener("click", () => {
    document.getElementById("onboarding-overlay")?.classList.add("hidden");
    openGedcomModal();
  });

  dropZone?.addEventListener("click", (e) => {
    if (e.target !== fileInput && e.target.tagName !== "LABEL") fileInput.click();
  });
  dropZone?.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
  dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) handleGedcomFile(e.dataTransfer.files[0]);
  });
  fileInput?.addEventListener("change", () => {
    if (fileInput.files.length > 0) handleGedcomFile(fileInput.files[0]);
    fileInput.value = "";
  });

  async function handleGedcomFile(file) {
    statusEl.classList.remove("hidden");
    statusText.textContent = `Importing ${file.name}...`;

    const formData = new FormData();
    formData.append("file", file);

    let resp;
    try {
      resp = await fetch("/api/import/gedcom", { method: "POST", body: formData });
    } catch (err) {
      showToast("Import failed: " + err.message, "error");
      statusEl.classList.add("hidden");
      return;
    }

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      showToast(data.error || `Import failed (HTTP ${resp.status})`, "error");
      statusEl.classList.add("hidden");
      return;
    }

    const parts = [];
    if (data.people) parts.push(`${data.people} people`);
    if (data.unions) parts.push(`${data.unions} unions`);
    if (data.relationships) parts.push(`${data.relationships} relationships`);
    if (data.events) parts.push(`${data.events} events`);
    showToast(`Imported ${parts.join(", ")}`, "success");

    if (data.skipped?.length) {
      console.warn("GEDCOM import skipped:", data.skipped);
    }

    statusEl.classList.add("hidden");
    closeGedcomModal();

    // Reload data and re-render
    await loadData();
    buildLaneCache();
    updateStats();
    renderTree();
    renderTimeline();
    populateTimelineFilter();
    populateRelSelectors();
  }
})();

// ═══════════════════════════════════════════════════════════════
// Onboarding Wizard (empty tree)
// ═══════════════════════════════════════════════════════════════

(function initOnboarding() {
  const overlay = document.getElementById("onboarding-overlay");
  if (!overlay) return;

  // Show onboarding after init if tree is empty
  const origInit = window._ft_init_done;
  function maybeShowOnboarding() {
    if (S.DATA && S.DATA.people && S.DATA.people.length === 0) {
      overlay.classList.remove("hidden");
    }
  }
  // Hook into init — we'll call this from init()
  window._showOnboardingIfEmpty = maybeShowOnboarding;

  let currentStep = 1;
  let createdPersonId = null;

  function showStep(n) {
    currentStep = n;
    for (let i = 1; i <= 3; i++) {
      const stepEl = document.getElementById(`onboard-step-${i}`);
      const dotEl = overlay.querySelector(`.step-dot[data-step="${i}"]`);
      if (stepEl) stepEl.classList.toggle("active", i === n);
      if (dotEl) dotEl.classList.toggle("active", i <= n);
    }
  }

  async function createPerson(given, surname, gender, birth) {
    const id = (given + "-" + surname).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "") || "person-" + Date.now();
    const body = { id, given_name: given, surname, gender };
    if (birth) body.birth_date = birth;
    const resp = await fetch("/api/people", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${resp.status}`);
    }
    return id;
  }

  async function createRelationship(parentId, childId) {
    await fetch("/api/relationships", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent_id: parentId, child_id: childId }),
    });
  }

  async function createUnion(id1, id2) {
    await fetch("/api/unions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ partner1_id: id1, partner2_id: id2 }),
    });
  }

  // Step 1: Add yourself
  document.getElementById("onboard-next-1")?.addEventListener("click", async () => {
    const given = document.getElementById("onboard-given").value.trim();
    if (!given) { showToast("Please enter your first name", "error"); return; }
    const surname = document.getElementById("onboard-surname").value.trim();
    const gender = document.getElementById("onboard-gender").value;
    const birth = document.getElementById("onboard-birth").value.trim();
    try {
      createdPersonId = await createPerson(given, surname, gender, birth);
      showToast(`Added ${given}!`);
      showStep(2);
    } catch (e) {
      showToast("Error: " + e.message, "error");
    }
  });

  // Step 2: Add partner
  document.getElementById("onboard-next-2")?.addEventListener("click", async () => {
    const given = document.getElementById("onboard-partner-given").value.trim();
    if (!given) { showToast("Please enter a name or skip", "error"); return; }
    const surname = document.getElementById("onboard-partner-surname").value.trim();
    const gender = document.getElementById("onboard-partner-gender").value;
    const birth = document.getElementById("onboard-partner-birth").value.trim();
    try {
      const partnerId = await createPerson(given, surname, gender, birth);
      if (createdPersonId) await createUnion(createdPersonId, partnerId);
      showToast(`Added ${given}!`);
      showStep(3);
    } catch (e) {
      showToast("Error: " + e.message, "error");
    }
  });
  document.getElementById("onboard-skip-2")?.addEventListener("click", () => showStep(3));

  // Step 3: Add parent
  document.getElementById("onboard-finish")?.addEventListener("click", async () => {
    const given = document.getElementById("onboard-parent-given").value.trim();
    if (given) {
      const surname = document.getElementById("onboard-parent-surname").value.trim();
      const gender = document.getElementById("onboard-parent-gender").value;
      const birth = document.getElementById("onboard-parent-birth").value.trim();
      try {
        const parentId = await createPerson(given, surname, gender, birth);
        if (createdPersonId) await createRelationship(parentId, createdPersonId);
        showToast(`Added ${given}!`);
      } catch (e) {
        showToast("Error: " + e.message, "error");
      }
    }
    finishOnboarding();
  });
  document.getElementById("onboard-skip-3")?.addEventListener("click", finishOnboarding);
  document.getElementById("onboard-skip-all")?.addEventListener("click", () => {
    overlay.classList.add("hidden");
  });

  async function finishOnboarding() {
    overlay.classList.add("hidden");
    showToast("Welcome to your family tree!", "success");
    await loadData();
    buildLaneCache();
    updateStats();
    renderTree();
    renderTimeline();
    populateTimelineFilter();
    populateRelSelectors();
  }
})();

// ── Review Modal ──────────────────────────────────────────────────────

export function openReviewModal(proposed, filename, alreadyApplied) {
  const overlay = document.getElementById("doc-review-overlay");
  const title = document.getElementById("doc-review-title");
  const summary = document.getElementById("doc-review-summary");
  const body = document.getElementById("doc-review-body");
  const applyBtn = document.getElementById("doc-review-apply");
  if (alreadyApplied) {
    applyBtn.textContent = "Re-apply Changes";
  } else {
    applyBtn.textContent = "Apply Changes";
  }

  title.textContent = `Review — ${filename}`;
  summary.textContent = proposed.summary || "AI extracted the following information.";

  let html = "";

  // People section
  const people = proposed.people || [];
  if (people.length > 0) {
    html += `<div class="review-section">`;
    html += `<div class="review-section-title">People (${people.length})</div>`;
    for (let i = 0; i < people.length; i++) {
      const p = people[i];
      const badge = p.is_new
        ? `<span class="new-badge">NEW</span>`
        : `<span class="update-badge">UPDATE</span>`;
      html += `<div class="review-card">`;
      html += `<div><span class="value">${p.given_name || ""} ${p.surname || ""}</span>${badge}</div>`;
      html += `<div><span class="label">ID: </span><input value="${p.id || ""}" data-path="people.${i}.id" /></div>`;
      if (p.birth_date) html += `<div><span class="label">Born: </span><input value="${p.birth_date}" data-path="people.${i}.birth_date" /></div>`;
      if (p.birth_place) html += `<div><span class="label">Birth place: </span><input value="${p.birth_place}" data-path="people.${i}.birth_place" /></div>`;
      if (p.death_date) html += `<div><span class="label">Died: </span><input value="${p.death_date}" data-path="people.${i}.death_date" /></div>`;
      if (p.death_place) html += `<div><span class="label">Death place: </span><input value="${p.death_place}" data-path="people.${i}.death_place" /></div>`;
      if (p.maiden_name) html += `<div><span class="label">Maiden name: </span><input value="${p.maiden_name}" data-path="people.${i}.maiden_name" /></div>`;
      if (p.notes) html += `<div><span class="label">Notes: </span><input value="${p.notes.replace(/"/g, '&quot;')}" data-path="people.${i}.notes" /></div>`;
      html += `</div>`;
    }
    html += `</div>`;
  }

  // Relationships section
  const rels = proposed.relationships || [];
  if (rels.length > 0) {
    html += `<div class="review-section">`;
    html += `<div class="review-section-title">Relationships (${rels.length})</div>`;
    for (const r of rels) {
      const pName = _nameForId(r.parent_id);
      const cName = _nameForId(r.child_id);
      html += `<div class="review-card">${pName} &rarr; ${cName} <span class="label">(${r.rel_type || "biological"})</span></div>`;
    }
    html += `</div>`;
  }

  // Events section
  const events = proposed.events || [];
  if (events.length > 0) {
    html += `<div class="review-section">`;
    html += `<div class="review-section-title">Events (${events.length})</div>`;
    for (const ev of events) {
      const eName = _nameForId(ev.person_id);
      html += `<div class="review-card">${eName}: ${ev.event_type}${ev.date ? " — " + ev.date : ""}${ev.place ? " @ " + ev.place : ""}${ev.description ? "<br/>" + ev.description : ""}</div>`;
    }
    html += `</div>`;
  }

  // Unions section
  const unions = proposed.unions || [];
  if (unions.length > 0) {
    html += `<div class="review-section">`;
    html += `<div class="review-section-title">Marriages/Partnerships (${unions.length})</div>`;
    for (const u of unions) {
      const p1 = _nameForId(u.partner1_id);
      const p2 = _nameForId(u.partner2_id);
      html += `<div class="review-card">${p1} &amp; ${p2}${u.union_date ? " — " + u.union_date : ""}</div>`;
    }
    html += `</div>`;
  }

  // Notes
  if (proposed.notes) {
    html += `<div class="review-notes">${proposed.notes}</div>`;
  }

  if (!html) {
    html = `<p style="color:var(--text-muted);text-align:center;padding:24px 0;">No structured data was extracted from this document.</p>`;
  }

  body.innerHTML = html;
  overlay.classList.remove("hidden");
}

export function _nameForId(id) {
  if (!id) return "?";
  // Try to find in existing people
  const p = S.PEOPLE_MAP[id];
  if (p) return p.fullName;
  // For new people, try to look up in proposed changes
  if (CURRENT_PROPOSED && CURRENT_PROPOSED.people) {
    const found = CURRENT_PROPOSED.people.find((pp) => pp.id === id);
    if (found) return `${found.given_name || ""} ${found.surname || ""}`.trim() || id;
  }
  return id;
}

// Review modal: Apply button
document.getElementById("doc-review-apply")?.addEventListener("click", async () => {
  if (!CURRENT_DOC_ID || !CURRENT_PROPOSED) return;

  const applyBtn = document.getElementById("doc-review-apply");
  applyBtn.disabled = true;
  applyBtn.textContent = "Applying...";

  // Read any edits from the review form inputs
  const inputs = document.querySelectorAll("#doc-review-body input[data-path]");
  for (const inp of inputs) {
    const path = inp.dataset.path;
    const parts = path.split(".");
    // e.g. "people.0.birth_date"
    let obj = CURRENT_PROPOSED;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = isNaN(parts[i]) ? parts[i] : parseInt(parts[i]);
      obj = obj[key];
    }
    obj[parts[parts.length - 1]] = inp.value;
  }

  try {
    const resp = await fetch(`/api/documents/${CURRENT_DOC_ID}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(CURRENT_PROPOSED),
    });
    const data = await resp.json();

    if (resp.ok) {
      const a = data.applied;
      const parts = [];
      if (a.people) parts.push(`${a.people} people`);
      if (a.relationships) parts.push(`${a.relationships} relationships`);
      if (a.events) parts.push(`${a.events} events`);
      if (a.unions) parts.push(`${a.unions} unions`);
      showToast(`Applied: ${parts.join(", ") || "no changes"}`);

      // Refresh data
      await loadData();
      if (typeof applyFocus === "function") applyFocus();
    } else {
      showToast(data.error || "Apply failed", "error");
    }
  } catch (err) {
    showToast("Apply failed: " + err.message, "error");
  }

  applyBtn.disabled = false;
  applyBtn.textContent = "Apply Changes";
  document.getElementById("doc-review-overlay").classList.add("hidden");
  CURRENT_DOC_ID = null;
  CURRENT_PROPOSED = null;
});

// Review modal: Cancel / close
document.getElementById("doc-review-cancel")?.addEventListener("click", () => {
  document.getElementById("doc-review-overlay").classList.add("hidden");
  CURRENT_DOC_ID = null;
  CURRENT_PROPOSED = null;
});
document.getElementById("doc-review-close")?.addEventListener("click", () => {
  document.getElementById("doc-review-overlay").classList.add("hidden");
});
document.getElementById("doc-review-overlay")?.addEventListener("click", (e) => {
  if (e.target.id === "doc-review-overlay") {
    e.target.classList.add("hidden");
  }
});

// ═══════════════════════════════════════════════════════════════
// Photo Picker
// ═══════════════════════════════════════════════════════════════

