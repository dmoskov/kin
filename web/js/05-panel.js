// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

function _calcAge(birthDate, deathDate) {
  if (!birthDate) return null;
  const bYear = parseInt(birthDate, 10);
  if (isNaN(bYear)) return null;
  const endDate = deathDate || new Date().toISOString().slice(0, 10);
  const eYear = parseInt(endDate, 10);
  if (isNaN(eYear)) return null;
  return eYear - bYear;
}

const _EVENT_ICONS = {
  birth: "✶", death: "✝", marriage: "♡",
  career: "⚒", education: "⌂", immigration: "✈",
  residence: "⌂", military: "⚔", custom: "★",
};
function _eventIcon(type) {
  return _EVENT_ICONS[type] || _EVENT_ICONS.custom;
}

const _EVENT_COLORS = {
  birth: "--event-birth", death: "--text-muted", marriage: "--event-marriage",
  career: "--event-career", education: "--event-education",
  immigration: "--accent", military: "--text-muted", custom: "--event-custom",
};
function _eventColorVar(type) {
  return _EVENT_COLORS[type] || _EVENT_COLORS.custom;
}

export function showPersonPanel(personId) {
  const person = S.PEOPLE_MAP[personId];
  if (!person) return;

  const panel = document.getElementById("person-panel");
  const content = document.getElementById("panel-content");

  // Find family connections
  const parents = S.DATA.relationships
    .filter((r) => r.child_id === personId)
    .map((r) => r.parent_id);
  const children = S.DATA.relationships
    .filter((r) => r.parent_id === personId)
    .map((r) => r.child_id);
  const partners = S.DATA.unions
    .filter((u) => u.partner1_id === personId || u.partner2_id === personId)
    .map((u) => (u.partner1_id === personId ? u.partner2_id : u.partner1_id));
  const events = S.DATA.events
    .filter((e) => e.person_id === personId)
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  // Show viewer-relative relationship if a viewer is set and this isn't the viewer
  let relBadge = "";
  if (S.CENTER_ID_A && personId !== S.CENTER_ID_A) {
    const relLabel = calculateRelationship(S.CENTER_ID_A, personId);
    if (relLabel && relLabel !== "no relation found") {
      relBadge = `<div class="panel-rel-badge">Your ${relLabel}</div>`;
    }
  }

  // Hero header with large avatar
  const heroSize = 80;
  const heroThumb = personThumb(personId, heroSize);

  // Lifespan string with age
  let lifespanHtml = "";
  if (person.birth_date || person.death_date) {
    const parts = [];
    if (person.birth_date) parts.push(escapeHtml(person.birth_date));
    if (person.death_date) parts.push(escapeHtml(person.death_date));
    else if (person.birth_date) parts.push("present");
    const age = _calcAge(person.birth_date, person.death_date);
    const ageStr = age !== null ? ` · age ${age}` : "";
    lifespanHtml = `<div class="panel-lifespan">${parts.join(" – ")}${ageStr}</div>`;
  }

  let html = `
    <div class="panel-hero">
      <div class="panel-hero-avatar">${heroThumb}</div>
      <div class="panel-hero-info">
        <div class="panel-name">${escapeHtml(person.fullName)}</div>
        ${relBadge}
        <div class="panel-hero-meta">
          <span class="panel-gender ${escapeHtml(person.gender)}">${escapeHtml(person.gender)}</span>
          ${!S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor ? `<button class="panel-edit-btn" onclick="openEditPersonForm('${personId}')">Edit</button>` : ""}
        </div>
        ${lifespanHtml}
      </div>
    </div>
    <div id="edit-person-form" class="add-relative-form hidden"></div>
  `;

  // Photos + Manage Photos button. The inner markup is shared with
  // _renderPanelPhotos (the picker-refresh path) via buildPanelPhotosInnerHtml.
  html += `<div class="panel-photos-section">`;
  html += buildPanelPhotosInnerHtml(personId);
  html += `</div>`;

  // Heritage badge for panel
  const panelHeritage = matchHeritage(person.birth_place);
  if (panelHeritage && S.CONFIG?.heritageLabels !== false) {
    html += `<span class="panel-heritage-badge" style="color:${panelHeritage.color};border:1px solid ${panelHeritage.color}40;margin-top:8px">${panelHeritage.region}</span>`;
  }

  // Vital stats
  if (person.birth_date || person.birth_place || person.maiden_name) {
    html += `<div class="panel-section"><h3>Details</h3><div class="panel-details-grid">`;
    if (person.birth_date) {
      html += `<div class="panel-detail-item"><span class="panel-detail-icon">&#9679;</span><div class="panel-detail-body"><span class="panel-detail-label">Born</span><span class="panel-detail-value">${escapeHtml(person.birth_date)}${person.birth_place ? " · " + escapeHtml(person.birth_place) : ""}</span></div></div>`;
    }
    if (person.death_date) {
      html += `<div class="panel-detail-item"><span class="panel-detail-icon" style="color:var(--text-muted)">&#9679;</span><div class="panel-detail-body"><span class="panel-detail-label">Died</span><span class="panel-detail-value">${escapeHtml(person.death_date)}${person.death_place ? " · " + escapeHtml(person.death_place) : ""}</span></div></div>`;
    }
    if (person.maiden_name) {
      html += `<div class="panel-detail-item"><span class="panel-detail-icon" style="color:var(--text-muted)">&#9679;</span><div class="panel-detail-body"><span class="panel-detail-label">Maiden name</span><span class="panel-detail-value">${escapeHtml(person.maiden_name)}</span></div></div>`;
    }
    if (person.email) {
      html += `<div class="panel-detail-item"><span class="panel-detail-icon" style="color:var(--text-muted)">&#9679;</span><div class="panel-detail-body"><span class="panel-detail-label">Email</span><span class="panel-detail-value">${escapeHtml(person.email)}</span></div></div>`;
    }
    html += `</div></div>`;
  }

  // Siblings
  const siblingIds = new Set();
  const myParents = S.DATA.relationships.filter(r => r.child_id === personId).map(r => r.parent_id);
  for (const pid of myParents) {
    S.DATA.relationships.filter(r => r.parent_id === pid && r.child_id !== personId)
      .forEach(r => siblingIds.add(r.child_id));
  }
  const siblings = [...siblingIds];

  // Family
  if (parents.length || children.length || partners.length || siblings.length) {
    html += `<div class="panel-section"><h3>Family</h3><ul class="panel-family-list">`;
    for (const pid of parents) {
      html += `<li><a class="person-link" data-person-id="${pid}" href="javascript:void(0)">${personThumb(pid, 28)} ${personName(pid)}</a> <span class="panel-rel-pill panel-rel-parent">parent</span></li>`;
    }
    for (const pid of siblings) {
      html += `<li><a class="person-link" data-person-id="${pid}" href="javascript:void(0)">${personThumb(pid, 28)} ${personName(pid)}</a> <span class="panel-rel-pill panel-rel-sibling">sibling</span></li>`;
    }
    for (const pid of partners) {
      html += `<li><a class="person-link" data-person-id="${pid}" href="javascript:void(0)">${personThumb(pid, 28)} ${personName(pid)}</a> <span class="panel-rel-pill panel-rel-partner">partner</span></li>`;
    }
    for (const cid of children) {
      html += `<li><a class="person-link" data-person-id="${cid}" href="javascript:void(0)">${personThumb(cid, 28)} ${personName(cid)}</a> <span class="panel-rel-pill panel-rel-child">child</span></li>`;
    }
    html += `</ul></div>`;
  }

  // Add relative buttons (editors only)
  if (!S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor) {
    html += `<div class="panel-section panel-add-relative-section">
      <h3>Add Relative</h3>
      <div class="panel-add-relative-btns">
        <button class="panel-add-relative-btn" onclick="openAddRelativeForm('${personId}', 'parent')">+ Parent</button>
        <button class="panel-add-relative-btn" onclick="openAddRelativeForm('${personId}', 'sibling')">+ Sibling</button>
        <button class="panel-add-relative-btn" onclick="openAddRelativeForm('${personId}', 'child')">+ Child</button>
        <button class="panel-add-relative-btn" onclick="openAddRelativeForm('${personId}', 'partner')">+ Partner</button>
      </div>
      <div id="add-relative-form" class="add-relative-form hidden"></div>
    </div>`;
  }

  // Life events + dated photos merged into one timeline
  const personPhotos = (S.DATA.photos || []).filter((p) =>
    p.date && (p.tagged_people || []).some((tp) => tp.person_id === personId)
  );
  const timelineItems = [
    ...events.map((e) => ({ kind: "event", date: e.date || "", sortDate: e.date || "9999", ...e })),
    ...personPhotos.map((p) => {
      const tag = (p.tagged_people || []).find((tp) => tp.person_id === personId);
      return {
        kind: "photo",
        date: p.date,
        sortDate: p.date,
        description: tag?.caption || `Photo — ${p.date}`,
        place: p.place,
        photoPath: p.file_path,
      };
    }),
  ].sort((a, b) => (a.sortDate || "").localeCompare(b.sortDate || ""));

  if (timelineItems.length) {
    html += `<div class="panel-section"><h3>Life Events</h3><div class="panel-events-timeline">`;
    for (const e of timelineItems) {
      const date = e.date ? e.date.substring(0, 7) : "?";
      const icon = e.kind === "photo" ? "📷" : _eventIcon(e.event_type);
      const colorVar = e.kind === "photo" ? "--event-custom" : _eventColorVar(e.event_type);
      const photoThumb = e.kind === "photo" && e.photoPath
        ? `<img class="panel-event-photo" src="/${e.photoPath}" alt="" loading="lazy" onclick="openLightbox('/${e.photoPath}', '${(e.description || "").replace(/'/g, "\\'")}', '${e.photoPath}')" />`
        : "";
      html += `
        <div class="panel-event">
          <div class="panel-event-marker" style="--marker-color:var(${colorVar})">
            <span class="panel-event-icon">${icon}</span>
            <span class="panel-event-line"></span>
          </div>
          <div class="panel-event-body">
            <span class="panel-event-date">${date}</span>
            <span class="panel-event-desc">${escapeHtml(e.description || e.event_type)}${e.place ? " · <span class='panel-event-place'>" + escapeHtml(e.place) + "</span>" : ""}${e.source && e.source.startsWith("http") ? ` · <a class="panel-event-source" href="${escapeHtml(e.source)}" target="_blank" rel="noopener">source</a>` : ""}</span>
            ${photoThumb}
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  // Notes
  if (person.notes) {
    html += `<div class="panel-section"><h3>Notes</h3><div class="panel-notes">${escapeHtml(person.notes)}</div></div>`;
  }

  content.innerHTML = html;
  panel.classList.remove("hidden");
  requestAnimationFrame(() => panel.classList.add("panel-open"));
  if (S.MAP) setTimeout(() => S.MAP.invalidateSize(), 250);
  // On the tree, pan the selected node into the visible area if the panel now
  // covers it (or it's off-screen). No-op on other views.
  if (typeof activeViewName === "function" && activeViewName() === "tree") {
    ensureTreeNodeVisible(personId);
  }
}

document.getElementById("close-panel").addEventListener("click", () => {
  closePersonPanel();
  const view = activeViewName();
  const routeMap = { tree: "/tree", timeline: "/timeline", map: "/map" };
  router.navigate(routeMap[view] || "/tree");
});

// ═══════════════════════════════════════════════════════════════
// Add Relative Form
// ═══════════════════════════════════════════════════════════════

export function openAddRelativeForm(personId, relationship) {
  const form = document.getElementById("add-relative-form");
  if (!form) return;

  const label = { parent: "Parent", sibling: "Sibling", child: "Child", partner: "Partner" }[relationship] || relationship;
  form.innerHTML = `
    <div class="add-relative-form-inner">
      <div class="arf-mode-toggle">
        <button class="arf-mode-btn active" data-mode="create" onclick="switchAddRelativeMode('${personId}', '${relationship}', 'create')">Create New</button>
        <button class="arf-mode-btn" data-mode="link" onclick="switchAddRelativeMode('${personId}', '${relationship}', 'link')">Link Existing</button>
      </div>
      <div id="arf-create-section">
        <div class="add-relative-row">
          <input id="arf-given" type="text" placeholder="First name" class="add-relative-input" />
          <input id="arf-surname" type="text" placeholder="Last name" class="add-relative-input" />
        </div>
        <div class="add-relative-row">
          <select id="arf-gender" class="add-relative-input">
            <option value="unknown">Gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
          <input id="arf-birth" type="text" placeholder="Birth year (optional)" class="add-relative-input" />
        </div>
        <div class="add-relative-row">
          <input id="arf-death" type="text" placeholder="Death year (optional)" class="add-relative-input" />
        </div>
        <div class="add-relative-actions">
          <button class="add-relative-submit" onclick="submitAddRelative('${personId}', '${relationship}')">Add ${label}</button>
          <button class="add-relative-cancel" onclick="document.getElementById('add-relative-form').classList.add('hidden')">Cancel</button>
        </div>
      </div>
      <div id="arf-link-section" class="hidden">
        <div class="add-relative-row">
          <div class="arf-search-wrapper">
            <input id="arf-search" type="text" placeholder="Search by name…" class="add-relative-input" autocomplete="off" oninput="filterLinkCandidates('${personId}', '${relationship}')" />
            <div id="arf-search-results" class="arf-search-results hidden"></div>
          </div>
        </div>
        <div id="arf-selected-person" class="arf-selected-person hidden"></div>
        <div class="add-relative-actions">
          <button id="arf-link-submit" class="add-relative-submit" disabled onclick="submitLinkExisting('${personId}', '${relationship}')">Link as ${label}</button>
          <button class="add-relative-cancel" onclick="document.getElementById('add-relative-form').classList.add('hidden')">Cancel</button>
        </div>
      </div>
      <div id="arf-error" class="add-relative-error hidden"></div>
    </div>
  `;
  form.classList.remove("hidden");
  document.getElementById("arf-given").focus();
}

let _arfSelectedPersonId = null;

export function switchAddRelativeMode(personId, relationship, mode) {
  const createSection = document.getElementById("arf-create-section");
  const linkSection = document.getElementById("arf-link-section");
  if (!createSection || !linkSection) return;

  document.querySelectorAll(".arf-mode-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });

  if (mode === "create") {
    createSection.classList.remove("hidden");
    linkSection.classList.add("hidden");
    document.getElementById("arf-given")?.focus();
  } else {
    createSection.classList.add("hidden");
    linkSection.classList.remove("hidden");
    _arfSelectedPersonId = null;
    const sel = document.getElementById("arf-selected-person");
    if (sel) { sel.classList.add("hidden"); sel.innerHTML = ""; }
    const btn = document.getElementById("arf-link-submit");
    if (btn) btn.disabled = true;
    document.getElementById("arf-search")?.focus();
  }
  const errorEl = document.getElementById("arf-error");
  if (errorEl) errorEl.classList.add("hidden");
}

export function _getLinkExcludeIds(personId, relationship) {
  const exclude = new Set([personId]);
  if (relationship === "parent") {
    S.DATA.relationships.filter(r => r.child_id === personId).forEach(r => exclude.add(r.parent_id));
  } else if (relationship === "child") {
    S.DATA.relationships.filter(r => r.parent_id === personId).forEach(r => exclude.add(r.child_id));
  } else if (relationship === "sibling") {
    const parentIds = S.DATA.relationships.filter(r => r.child_id === personId).map(r => r.parent_id);
    for (const pid of parentIds) {
      S.DATA.relationships.filter(r => r.parent_id === pid).forEach(r => exclude.add(r.child_id));
    }
  } else if (relationship === "partner") {
    S.DATA.unions.filter(u => u.partner1_id === personId || u.partner2_id === personId)
      .forEach(u => { exclude.add(u.partner1_id); exclude.add(u.partner2_id); });
  }
  return exclude;
}

export function filterLinkCandidates(personId, relationship) {
  const input = document.getElementById("arf-search");
  const resultsEl = document.getElementById("arf-search-results");
  if (!input || !resultsEl) return;

  const q = input.value.trim();
  if (!q) { resultsEl.classList.add("hidden"); return; }

  // Search the full person set (not the focus-filtered S.DATA) so any existing
  // person can be linked, with the shared ranked matcher.
  const exclude = _getLinkExcludeIds(personId, relationship);
  const candidates = Object.values(S.PEOPLE_MAP).filter((p) => !exclude.has(p.id));
  const matches = rankPeople(q, candidates, 10);

  if (matches.length === 0) {
    resultsEl.innerHTML = `<div class="arf-search-empty">No matches found</div>`;
    resultsEl.classList.remove("hidden");
    return;
  }

  resultsEl.innerHTML = matches.map(p => {
    const dates = [p.birth_date, p.death_date].filter(Boolean).join(" – ");
    return `<div class="arf-search-item" onclick="selectLinkPerson('${p.id}', '${personId}', '${relationship}')">
      ${personThumb(p.id, 28)}
      <div class="arf-search-item-info">
        <span class="arf-search-item-name">${personName(p.id)}</span>
        ${dates ? `<span class="arf-search-item-dates">${dates}</span>` : ""}
      </div>
    </div>`;
  }).join("");
  resultsEl.classList.remove("hidden");
}

export function selectLinkPerson(selectedId, personId, relationship) {
  _arfSelectedPersonId = selectedId;
  const resultsEl = document.getElementById("arf-search-results");
  if (resultsEl) resultsEl.classList.add("hidden");
  const input = document.getElementById("arf-search");
  if (input) input.value = "";

  const selEl = document.getElementById("arf-selected-person");
  if (selEl) {
    const p = S.PEOPLE_MAP[selectedId];
    const dates = [p?.birth_date, p?.death_date].filter(Boolean).join(" – ");
    selEl.innerHTML = `
      ${personThumb(selectedId, 32)}
      <div class="arf-search-item-info">
        <span class="arf-search-item-name">${personName(selectedId)}</span>
        ${dates ? `<span class="arf-search-item-dates">${dates}</span>` : ""}
      </div>
      <button class="arf-selected-remove" onclick="clearLinkSelection('${personId}', '${relationship}')">&times;</button>
    `;
    selEl.classList.remove("hidden");
  }
  const btn = document.getElementById("arf-link-submit");
  if (btn) btn.disabled = false;
}

export function clearLinkSelection(personId, relationship) {
  _arfSelectedPersonId = null;
  const selEl = document.getElementById("arf-selected-person");
  if (selEl) { selEl.classList.add("hidden"); selEl.innerHTML = ""; }
  const btn = document.getElementById("arf-link-submit");
  if (btn) btn.disabled = true;
  document.getElementById("arf-search")?.focus();
}

export function _arfShowError(errorEl, msg) {
  if (errorEl) {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
  }
}

export function _siblingParentIds(personId) {
  return S.DATA.relationships.filter((r) => r.child_id === personId).map((r) => r.parent_id);
}

// Create the union/relationship(s) linking relativeId to personId, then reload
// and refresh. Shared by submitLinkExisting and submitAddRelative. Returns true
// on success, false after showing an error.
export async function linkRelative(personId, relationship, relativeId, errorEl) {
  if (relationship === "partner") {
    try {
      const res = await fetch("/api/unions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ partner1_id: personId, partner2_id: relativeId }),
      });
      if (!res.ok) {
        const data = await res.json();
        _arfShowError(errorEl, data.error || "Failed to create union.");
        return false;
      }
    } catch {
      _arfShowError(errorEl, "Network error creating union.");
      return false;
    }
  } else {
    const relPairs = [];
    if (relationship === "parent") {
      relPairs.push({ parent_id: relativeId, child_id: personId });
    } else if (relationship === "child") {
      relPairs.push({ parent_id: personId, child_id: relativeId });
    } else if (relationship === "sibling") {
      const parents = _siblingParentIds(personId);
      for (const pid of parents) {
        relPairs.push({ parent_id: pid, child_id: relativeId });
      }
      if (relPairs.length === 0) {
        _arfShowError(errorEl, "Cannot add a sibling: this person has no parents. Add a parent first.");
        return false;
      }
    }

    try {
      for (const pair of relPairs) {
        const res = await fetch("/api/relationships", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(pair),
        });
        if (!res.ok) {
          const data = await res.json();
          _arfShowError(errorEl, data.error || "Failed to create relationship.");
          return false;
        }
      }
    } catch {
      _arfShowError(errorEl, "Network error creating relationship.");
      return false;
    }
  }

  await loadData();
  autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);
  refreshAllViews();
  showPersonPanel(personId);
  return true;
}

export async function submitLinkExisting(personId, relationship) {
  const errorEl = document.getElementById("arf-error");
  if (!_arfSelectedPersonId) {
    _arfShowError(errorEl, "Select a person first.");
    return;
  }
  await linkRelative(personId, relationship, _arfSelectedPersonId, errorEl);
}

export async function submitAddRelative(personId, relationship) {
  const givenName = document.getElementById("arf-given").value.trim();
  const surname = document.getElementById("arf-surname").value.trim();
  const gender = document.getElementById("arf-gender").value;
  const birthYear = document.getElementById("arf-birth").value.trim();
  const deathYear = document.getElementById("arf-death").value.trim();
  const errorEl = document.getElementById("arf-error");

  if (!givenName && !surname) {
    _arfShowError(errorEl, "Enter at least a first or last name.");
    return;
  }

  // Pre-flight: a sibling attaches to the focus person's existing parents, so
  // check that here — before creating the new person — to avoid leaving an
  // orphan record if the link can't be made.
  if (relationship === "sibling" && _siblingParentIds(personId).length === 0) {
    _arfShowError(errorEl, "Cannot add a sibling: this person has no parents. Add a parent first.");
    return;
  }

  const personPayload = { given_name: givenName, surname, gender };
  if (birthYear) personPayload.birth_date = birthYear;
  if (deathYear) personPayload.death_date = deathYear;

  let newPersonId;
  try {
    const res = await fetch("/api/people", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(personPayload),
    });
    const data = await res.json();
    if (!res.ok) {
      _arfShowError(errorEl, data.error || "Failed to create person.");
      return;
    }
    newPersonId = data.id;
  } catch {
    _arfShowError(errorEl, "Network error. Please try again.");
    return;
  }

  await linkRelative(personId, relationship, newPersonId, errorEl);
}

// ═══════════════════════════════════════════════════════════════
// Edit Person Form
// ═══════════════════════════════════════════════════════════════

export function openEditPersonForm(personId) {
  const form = document.getElementById("edit-person-form");
  if (!form) return;

  const person = S.PEOPLE_MAP[personId];
  if (!person) return;

  const esc = escapeHtml;

  form.innerHTML = `
    <div class="add-relative-form-inner">
      <div class="add-relative-row">
        <input id="epf-given" type="text" placeholder="First name" class="add-relative-input" value="${esc(person.given_name)}" />
        <input id="epf-surname" type="text" placeholder="Last name" class="add-relative-input" value="${esc(person.surname)}" />
      </div>
      <div class="add-relative-row">
        <select id="epf-gender" class="add-relative-input">
          <option value="unknown" ${person.gender === "unknown" ? "selected" : ""}>Gender</option>
          <option value="male" ${person.gender === "male" ? "selected" : ""}>Male</option>
          <option value="female" ${person.gender === "female" ? "selected" : ""}>Female</option>
        </select>
      </div>
      <div class="add-relative-row">
        <input id="epf-birth" type="text" placeholder="Birth date (e.g. 1987 or 1987-05-12)" class="add-relative-input" value="${esc(person.birth_date)}" />
        <input id="epf-birth-place" type="text" placeholder="Birth place (optional)" class="add-relative-input" value="${esc(person.birth_place)}" />
      </div>
      <div class="add-relative-row">
        <input id="epf-death" type="text" placeholder="Death date (optional)" class="add-relative-input" value="${esc(person.death_date)}" />
        <input id="epf-death-place" type="text" placeholder="Death place (optional)" class="add-relative-input" value="${esc(person.death_place)}" />
      </div>
      <div class="add-relative-actions">
        <button class="add-relative-submit" onclick="submitEditPerson('${personId}')">Save</button>
        <button class="add-relative-cancel" onclick="document.getElementById('edit-person-form').classList.add('hidden')">Cancel</button>
      </div>
      <div id="epf-error" class="add-relative-error hidden"></div>
    </div>
  `;
  form.classList.remove("hidden");
  document.getElementById("epf-given").focus();
}

export async function submitEditPerson(personId) {
  const givenName = document.getElementById("epf-given").value.trim();
  const surname = document.getElementById("epf-surname").value.trim();
  const gender = document.getElementById("epf-gender").value;
  const birthDate = document.getElementById("epf-birth").value.trim();
  const birthPlace = document.getElementById("epf-birth-place").value.trim();
  const deathDate = document.getElementById("epf-death").value.trim();
  const deathPlace = document.getElementById("epf-death-place").value.trim();
  const errorEl = document.getElementById("epf-error");

  if (!givenName && !surname) {
    errorEl.textContent = "Enter at least a first or last name.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch(`/api/people/${personId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        given_name: givenName,
        surname,
        gender,
        birth_date: birthDate || null,
        birth_place: birthPlace || null,
        death_date: deathDate || null,
        death_place: deathPlace || null,
      }),
    });
    if (!res.ok) {
      const data = await res.json();
      errorEl.textContent = data.error || "Failed to save.";
      errorEl.classList.remove("hidden");
      return;
    }
  } catch {
    errorEl.textContent = "Network error. Please try again.";
    errorEl.classList.remove("hidden");
    return;
  }

  await loadData();
  autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);
  refreshAllViews();
  showPersonPanel(personId);
}

// ═══════════════════════════════════════════════════════════════
// Timeline View
// ═══════════════════════════════════════════════════════════════

