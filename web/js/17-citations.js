// Part of the family-tree web app (ES module).
// Citations rendered as subtle inline LINKS on the facts they back — not
// footnotes or a separate "Sources" list. A cited fact gets a small 🔗 that
// opens the source (its URL) or shows the source on hover; editors can link a
// source in-context (picking an existing one or creating a new one inline) and
// unlink with a faint ×.
//
// Cross-module helpers (escapeHtml, afterMutate, api) are bridged onto window
// by 99-main.js and resolved as bare globals at call time.
import { S } from "./00-state.js";

function _canEditCitations() {
  return !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
}

function _sourceById(id) {
  return (S.DATA.sources || []).find((s) => s.id === id) || null;
}

// Match citations for an entity.
//   fields === "*"        → every citation on the entity
//   fields is an array    → citations whose field_name is in the list
//   fields omitted/null   → entity-level citations only (no field_name)
function _matchCitations(entityType, entityId, fields) {
  return (S.DATA.citations || []).filter((c) => {
    if (c.entity_type !== entityType || String(c.entity_id) !== String(entityId)) return false;
    if (fields === "*") return true;
    if (!fields) return !c.field_name;
    return c.field_name && fields.includes(c.field_name);
  });
}

function _citeLinkHtml(c, focusId) {
  const esc = window.escapeHtml;
  const s = _sourceById(c.source_id);
  const name = s ? s.name : c.source_id;
  const conf = c.confidence && c.confidence !== "confirmed" ? ` (${c.confidence})` : "";
  const tip = esc(name + conf + (c.excerpt ? " — " + c.excerpt : ""));
  const unlink = _canEditCitations()
    ? `<button class="cite-unlink" title="Unlink source" onclick="unlinkCitation(${c.id}, '${focusId}')">×</button>`
    : "";
  if (s && s.url) {
    return `<a class="cite-link" href="${esc(s.url)}" target="_blank" rel="noopener" title="${tip}">🔗</a>${unlink}`;
  }
  // No URL: a non-link marker that still reveals the source on hover.
  return `<span class="cite-link cite-link-nourl" title="${tip}">🔗</span>${unlink}`;
}

// Returns the inline citation links (+ an in-context "link source" affordance
// for editors) for a fact. Empty string when there's nothing to show.
//   opts.fields   — see _matchCitations
//   opts.addField — field_name a newly linked source attaches to (null = entity-level)
//   opts.focusId  — person id to reshow after a mutation
export function citeHtml(entityType, entityId, opts = {}) {
  const { fields = null, addField = null, focusId = "" } = opts;
  const cites = _matchCitations(entityType, entityId, fields);
  let inner = cites.map((c) => _citeLinkHtml(c, focusId)).join("");
  if (_canEditCitations()) {
    const f = addField ? `'${addField}'` : "null";
    inner += `<button class="cite-add" title="Link a source" onclick="openLinkSourceForm('${entityType}', '${entityId}', ${f}, '${focusId}')">+ source</button>`;
  }
  return inner ? `<span class="cite-group">${inner}</span>` : "";
}

export async function unlinkCitation(citationId, focusId) {
  if (!confirm("Unlink this source?")) return;
  try {
    const res = await window.api.del(`/api/citations/${citationId}`);
    if (!res.ok) return;
  } catch {
    return;
  }
  await window.afterMutate(focusId);
}

// In-context source linker: pick an existing source or create a new one inline,
// then create the citation. Hand-built (not EditForm) because of the
// pick-or-create conditional fields.
export function openLinkSourceForm(entityType, entityId, fieldName, focusId) {
  const panel = document.getElementById("panel-content");
  if (!panel) return;

  let container = document.getElementById("link-source-overlay");
  if (!container) {
    container = document.createElement("div");
    container.id = "link-source-overlay";
    container.className = "edit-event-overlay";
    panel.appendChild(container);
  }

  const esc = window.escapeHtml;
  const sources = (S.DATA.sources || []).slice().sort((a, b) => a.name.localeCompare(b.name));
  const sourceOptions = sources
    .map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`)
    .join("");

  container.innerHTML = `
    <div class="add-relative-form-inner">
      <h3 style="margin:0 0 10px">Link a source</h3>
      <div class="add-relative-row">
        <select id="ls-source" class="add-relative-input">
          <option value="__new__">+ New source…</option>
          ${sourceOptions}
        </select>
      </div>
      <div id="ls-new-fields" class="hidden">
        <div class="add-relative-row">
          <input id="ls-name" type="text" class="add-relative-input" placeholder="Source name (e.g. 1920 US Census)" />
        </div>
        <div class="add-relative-row">
          <input id="ls-url" type="text" class="add-relative-input" placeholder="URL (optional)" />
          <select id="ls-type" class="add-relative-input">
            <option value="document">Document</option>
            <option value="letter">Letter</option>
            <option value="oral">Oral history</option>
            <option value="public">Public record</option>
            <option value="direct">Direct knowledge</option>
            <option value="other" selected>Other</option>
          </select>
        </div>
      </div>
      <div class="add-relative-row">
        <select id="ls-confidence" class="add-relative-input">
          <option value="confirmed" selected>Confirmed</option>
          <option value="probable">Probable</option>
          <option value="uncertain">Uncertain</option>
          <option value="conflicting">Conflicting</option>
        </select>
      </div>
      <div class="add-relative-actions">
        <button class="add-relative-submit" id="ls-save">Link</button>
        <button class="add-relative-cancel" id="ls-cancel">Cancel</button>
      </div>
      <div id="ls-error" class="add-relative-error hidden"></div>
    </div>
  `;
  container.classList.remove("hidden");

  const sourceSel = document.getElementById("ls-source");
  const newFields = document.getElementById("ls-new-fields");
  const errorEl = document.getElementById("ls-error");
  const saveBtn = document.getElementById("ls-save");

  // Default to whichever path is available: create-new when there are no
  // existing sources yet, otherwise the first existing source.
  if (sources.length) {
    sourceSel.value = sources[0].id;
    newFields.classList.add("hidden");
  } else {
    sourceSel.value = "__new__";
    newFields.classList.remove("hidden");
  }

  const syncNewFields = () => {
    newFields.classList.toggle("hidden", sourceSel.value !== "__new__");
    if (sourceSel.value === "__new__") document.getElementById("ls-name")?.focus();
  };
  sourceSel.addEventListener("change", syncNewFields);

  document.getElementById("ls-cancel").addEventListener("click", () => container.remove());

  saveBtn.addEventListener("click", async () => {
    errorEl.classList.add("hidden");
    const creatingNew = sourceSel.value === "__new__";
    const confidence = document.getElementById("ls-confidence").value;

    const showError = (msg) => {
      errorEl.textContent = msg;
      errorEl.classList.remove("hidden");
    };

    saveBtn.disabled = true;
    try {
      let sourceId = sourceSel.value;
      if (creatingNew) {
        const name = document.getElementById("ls-name").value.trim();
        if (!name) {
          showError("Enter a source name.");
          saveBtn.disabled = false;
          return;
        }
        const url = document.getElementById("ls-url").value.trim();
        const sourceType = document.getElementById("ls-type").value;
        const sres = await window.api.post("/api/sources", {
          name,
          url: url || null,
          source_type: sourceType,
        });
        if (!sres.ok) {
          const d = await sres.json().catch(() => ({}));
          showError(d.error || "Failed to create source.");
          saveBtn.disabled = false;
          return;
        }
        sourceId = (await sres.json()).id;
      }

      const cres = await window.api.post("/api/citations", {
        source_id: sourceId,
        entity_type: entityType,
        entity_id: String(entityId),
        field_name: fieldName || null,
        confidence,
      });
      if (!cres.ok) {
        const d = await cres.json().catch(() => ({}));
        showError(d.error || "Failed to link source.");
        saveBtn.disabled = false;
        return;
      }
    } catch {
      showError("Network error. Please try again.");
      saveBtn.disabled = false;
      return;
    }

    container.remove();
    await window.afterMutate(focusId);
  });

  if (sources.length) sourceSel.focus();
  else document.getElementById("ls-name")?.focus();
}
