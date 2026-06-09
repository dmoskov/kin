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
  // Structured year/month/day input composing an ISO partial (YYYY,
  // YYYY-MM, or YYYY-MM-DD) into a hidden field, so _readField and every
  // caller stay unchanged. Approximate dates remain a separate
  // `date_circa` checkbox field. Non-ISO legacy values fall back to the
  // plain text input so nothing gets mangled.
  date(id, value, f) {
    const v = String(value ?? "");
    if (v && !/^\d{4}(-\d{2}(-\d{2})?)?$/.test(v)) {
      return FIELD_RENDERERS.text(id, value, f);
    }
    const [y = "", m = "", d = ""] = v.split("-");
    const label = f.label || "Date";
    const monthOpts = ['<option value="">Month</option>']
      .concat(
        EF_MONTHS.map((name, i) => {
          const mm = String(i + 1).padStart(2, "0");
          return `<option value="${mm}" ${mm === m ? "selected" : ""}>${name}</option>`;
        })
      )
      .join("");
    return `<span class="ef-date">
      <input id="${id}" type="hidden" value="${_esc(v)}" />
      <input type="text" class="add-relative-input ef-date-y" inputmode="numeric" maxlength="4" placeholder="${_esc(f.placeholder || "YYYY")}" value="${_esc(y)}" aria-label="${_esc(label)} year" />
      <select class="add-relative-input ef-date-m" aria-label="${_esc(label)} month" ${y ? "" : "disabled"}>${monthOpts}</select>
      <input type="text" class="add-relative-input ef-date-d" inputmode="numeric" maxlength="2" placeholder="DD" value="${_esc(d ? String(parseInt(d, 10)) : "")}" aria-label="${_esc(label)} day" ${m ? "" : "disabled"} />
    </span>`;
  },
  // Place input with suggestions from every place already in the tree —
  // keeps spellings consistent ("Boston, Massachusetts" vs "Boston, MA")
  // without a network round-trip.
  place(id, value, f) {
    _ensurePlaceDatalist();
    return `<input id="${id}" type="text" list="ef-place-options" autocomplete="off" class="add-relative-input" placeholder="${_esc(f.placeholder || f.label || "Place")}" value="${_esc(value)}" />`;
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

const EF_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Keep the hidden ISO value in sync with the year/month/day segments.
// Month unlocks once a 4-digit year exists; day unlocks once a month is
// chosen — so a partial date is always a VALID partial (YYYY or YYYY-MM).
export function _wireDateGroups(root) {
  root.querySelectorAll(".ef-date").forEach((group) => {
    const hidden = group.querySelector('input[type="hidden"]');
    const yEl = group.querySelector(".ef-date-y");
    const mEl = group.querySelector(".ef-date-m");
    const dEl = group.querySelector(".ef-date-d");
    if (!hidden || !yEl || !mEl || !dEl) return;
    const compose = () => {
      const y = yEl.value.trim();
      const m = mEl.value;
      const d = dEl.value.trim();
      mEl.disabled = !/^\d{4}$/.test(y);
      dEl.disabled = mEl.disabled || !m;
      let iso = "";
      if (!mEl.disabled) {
        iso = y;
        if (m) {
          iso += `-${m}`;
          if (/^\d{1,2}$/.test(d) && !dEl.disabled) iso += `-${d.padStart(2, "0")}`;
        }
      }
      hidden.value = iso;
    };
    for (const el of [yEl, mEl, dEl]) {
      el.addEventListener("input", compose);
      el.addEventListener("change", compose);
    }
  });
}

// Shared <datalist> of every place already used anywhere in the tree.
// Rebuilt on each form open so fresh edits show up immediately.
function _ensurePlaceDatalist() {
  let dl = document.getElementById("ef-place-options");
  if (!dl) {
    dl = document.createElement("datalist");
    dl.id = "ef-place-options";
    document.body.appendChild(dl);
  }
  const places = new Set();
  for (const p of S.DATA?.people || []) {
    if (p.birth_place) places.add(p.birth_place);
    if (p.death_place) places.add(p.death_place);
  }
  for (const e of S.DATA?.events || []) if (e.place) places.add(e.place);
  for (const u of S.DATA?.unions || []) if (u.union_place) places.add(u.union_place);
  dl.innerHTML = [...places]
    .sort()
    .map((p) => `<option value="${_esc(p)}"></option>`)
    .join("");
}

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
    _wireDateGroups(el);

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

// THE post-mutation refresh: every server write that changes tree data must
// end with afterMutate(), never a hand-rolled loadData/lanes/render sequence.
// It reloads S.DATA, reapplies the viewer visibility filter, recomputes
// lanes for the current center couple, and refreshes all views — keeping
// the derived state (S.DATA, S.LANES) consistent in one place, and giving
// Phase 5 a single seam to swap in optimistic/targeted updates.
export async function afterMutate(personId) {
  await window.loadData();
  // loadData replaces S.DATA with the full graph; re-hide links the current
  // viewer shouldn't see before anything reads it (matches init behavior).
  window.applyVisibilityFilter();
  window.autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);
  window.refreshAllViews();
  if (personId != null) window.showPersonPanel(personId);
}
