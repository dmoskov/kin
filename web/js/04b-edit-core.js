// Part of the family-tree web app (ES module).
// Reusable, schema-driven edit primitive shared by every edit surface.
//
// Before this module, each edit form (person, event, union, add-relative)
// hand-built its own innerHTML, duplicated validation, and ended with the
// same loadData → autoComputeLanes → refreshAllViews → showPersonPanel tail.
// EditForm centralizes all of that so a new editable surface is a field
// schema plus a save callback.
//
// Cross-module helpers (escapeHtml, loadData, autoComputeLanes,
// refreshAllViews, showPersonPanel) are bridged onto window by 99-main.js
// and resolved as bare globals at call time, matching the rest of the app.
import { S } from "./00-state.js";

let _formSeq = 0;

// ─── Field renderers ──────────────────────────────────────────────
// Each renderer returns the inner HTML for one field, given a unique
// DOM id and the current value. Inputs reuse the existing .add-relative-*
// styles so the visual language is unchanged.

function _esc(v) {
  return window.escapeHtml ? window.escapeHtml(v == null ? "" : String(v)) : (v == null ? "" : String(v));
}

const FIELD_RENDERERS = {
  text(id, value, f) {
    return `<input id="${id}" type="text" class="add-relative-input" placeholder="${_esc(f.placeholder || f.label || "")}" value="${_esc(value)}" />`;
  },
  email(id, value, f) {
    return `<input id="${id}" type="email" class="add-relative-input" placeholder="${_esc(f.placeholder || f.label || "")}" value="${_esc(value)}" />`;
  },
  textarea(id, value, f) {
    return `<textarea id="${id}" class="add-relative-input" placeholder="${_esc(f.placeholder || f.label || "")}" rows="${f.rows || 3}">${_esc(value)}</textarea>`;
  },
  // Date is plain text for now (same as today); Phase 4 swaps in a
  // structured year/month/day input here without touching any caller.
  date(id, value, f) {
    return `<input id="${id}" type="text" class="add-relative-input" placeholder="${_esc(f.placeholder || "e.g. 1987 or 1987-05-12")}" value="${_esc(value)}" />`;
  },
  // Place is plain text for now; Phase 4 swaps in geocoding autocomplete.
  place(id, value, f) {
    return `<input id="${id}" type="text" class="add-relative-input" placeholder="${_esc(f.placeholder || f.label || "Place")}" value="${_esc(value)}" />`;
  },
  enum(id, value, f) {
    const opts = (f.options || [])
      .map((o) => {
        const ov = typeof o === "string" ? o : o.value;
        const ol = typeof o === "string" ? o : o.label;
        const sel = String(value ?? "") === String(ov) ? "selected" : "";
        return `<option value="${_esc(ov)}" ${sel}>${_esc(ol)}</option>`;
      })
      .join("");
    return `<select id="${id}" class="add-relative-input">${opts}</select>`;
  },
  checkbox(id, value, f) {
    return `<label class="apf-circa-label"><input id="${id}" type="checkbox" ${value ? "checked" : ""} /> ${_esc(f.label || "")}</label>`;
  },
};

// ─── Value collection ─────────────────────────────────────────────

function _readField(id, f) {
  const el = document.getElementById(id);
  if (!el) return undefined;
  if (f.type === "checkbox") return el.checked;
  const raw = (el.value ?? "").trim();
  if (raw === "" && f.required !== true && f.keepEmpty !== true) return null;
  return raw;
}

// ─── EditForm ─────────────────────────────────────────────────────
//
// EditForm.open({
//   title,            // optional heading
//   fields,           // [{ key, type, label, placeholder, options, required, half }]
//   values,           // current values object
//   submitLabel,      // default "Save"
//   mount,            // { el, mode: 'toggle' | 'remove' }  where the form lives
//   onSave,           // async (payload) => Response   (fetch response)
//   validate,         // optional (payload) => errorString | null
//   onSuccess,        // async (payload, responseBody) => void  (refresh/UI)
//   onCancel,         // optional () => void
// })
//
// Fields are laid out two-per-row when f.half is true, otherwise full width.

export const EditForm = {
  open(cfg) {
    const mount = cfg.mount;
    if (!mount || !mount.el) {
      console.error("[EditForm] mount.el is required");
      return;
    }
    const el = mount.el;
    const prefix = `ef${++_formSeq}`;
    const fields = cfg.fields || [];

    // Build rows: consecutive half-width fields pair up.
    const rows = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      const id = `${prefix}-${f.key}`;
      const render = FIELD_RENDERERS[f.type] || FIELD_RENDERERS.text;
      const cell = render(id, (cfg.values || {})[f.key], f);
      const next = fields[i + 1];
      if (f.half && next && next.half) {
        const nid = `${prefix}-${next.key}`;
        const nrender = FIELD_RENDERERS[next.type] || FIELD_RENDERERS.text;
        rows.push(`<div class="add-relative-row">${cell}${nrender(nid, (cfg.values || {})[next.key], next)}</div>`);
        i++;
      } else {
        rows.push(`<div class="add-relative-row">${cell}</div>`);
      }
    }

    const titleHtml = cfg.title ? `<h3 style="margin:0 0 10px">${_esc(cfg.title)}</h3>` : "";
    el.innerHTML = `
      <div class="add-relative-form-inner">
        ${titleHtml}
        ${rows.join("\n")}
        <div class="add-relative-actions">
          <button class="add-relative-submit" id="${prefix}-save">${_esc(cfg.submitLabel || "Save")}</button>
          <button class="add-relative-cancel" id="${prefix}-cancel">Cancel</button>
        </div>
        <div id="${prefix}-error" class="add-relative-error hidden"></div>
      </div>
    `;
    el.classList.remove("hidden");

    const errorEl = document.getElementById(`${prefix}-error`);
    const saveBtn = document.getElementById(`${prefix}-save`);
    const cancelBtn = document.getElementById(`${prefix}-cancel`);

    const showError = (msg) => {
      errorEl.textContent = msg;
      errorEl.classList.remove("hidden");
    };
    const clearError = () => {
      errorEl.textContent = "";
      errorEl.classList.add("hidden");
    };

    const close = () => {
      if (mount.mode === "remove") {
        el.remove();
      } else {
        el.classList.add("hidden");
      }
    };

    cancelBtn.addEventListener("click", () => {
      close();
      if (cfg.onCancel) cfg.onCancel();
    });

    saveBtn.addEventListener("click", async () => {
      clearError();

      // Collect payload.
      const payload = {};
      for (const f of fields) payload[f.key] = _readField(`${prefix}-${f.key}`, f);

      // Built-in required validation.
      for (const f of fields) {
        if (f.required && !payload[f.key]) {
          showError(`${f.label || f.key} is required.`);
          return;
        }
      }
      // Custom validation.
      if (cfg.validate) {
        const err = cfg.validate(payload);
        if (err) {
          showError(err);
          return;
        }
      }

      saveBtn.disabled = true;
      const originalLabel = saveBtn.textContent;
      saveBtn.textContent = "Saving…";
      try {
        const res = await cfg.onSave(payload);
        if (!res || !res.ok) {
          let msg = "Failed to save.";
          try {
            const data = await res.json();
            if (data && data.error) msg = data.error;
          } catch (_) {}
          showError(msg);
          saveBtn.disabled = false;
          saveBtn.textContent = originalLabel;
          return;
        }
        let body = null;
        try {
          body = await res.json();
        } catch (_) {}
        close();
        if (cfg.onSuccess) await cfg.onSuccess(payload, body);
      } catch (err) {
        showError("Network error. Please try again.");
        saveBtn.disabled = false;
        saveBtn.textContent = originalLabel;
      }
    });

    // Focus the first focusable input.
    const first = fields.find((f) => f.type !== "checkbox");
    if (first) document.getElementById(`${prefix}-${first.key}`)?.focus();

    return { close, prefix };
  },
};

// ─── Shared mutation helpers ──────────────────────────────────────

// Thin JSON fetch wrappers so callers don't repeat headers/serialization.
export const api = {
  patch: (url, body) =>
    fetch(url, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  post: (url, body) =>
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  put: (url, body) =>
    fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  del: (url) => fetch(url, { method: "DELETE" }),
};

// The standard post-mutation refresh used by every panel edit today:
// reload data, recompute lanes, refresh all views, reshow the person panel.
// Centralized here so Phase 5 can swap in optimistic/targeted updates in
// one place instead of at every call site.
export async function afterMutate(personId) {
  await window.loadData();
  window.autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);
  window.refreshAllViews();
  if (personId != null) window.showPersonPanel(personId);
}
