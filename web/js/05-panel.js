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
  emigration: "✈", residence: "⌂", military: "⚔",
  naturalization: "⚑", religion: "✦", medical: "✚",
  custom: "★",
};
function _eventIcon(type) {
  return _EVENT_ICONS[type] || _EVENT_ICONS.custom;
}

const _EVENT_COLORS = {
  birth: "--event-birth", death: "--text-muted", marriage: "--event-marriage",
  career: "--event-career", education: "--event-education",
  immigration: "--accent", emigration: "--accent",
  residence: "--event-residence", military: "--text-muted",
  naturalization: "--accent", custom: "--event-custom",
};
function _eventColorVar(type) {
  return _EVENT_COLORS[type] || _EVENT_COLORS.custom;
}

const _EVENT_TYPE_LABELS = {
  birth: "Birth", death: "Death", marriage: "Marriage", divorce: "Divorce",
  immigration: "Immigration", emigration: "Emigration", naturalization: "Naturalization",
  education: "Education", career: "Career", military: "Military",
  residence: "Residence", religion: "Religion", medical: "Medical", custom: "Other",
};

function _formatEventDate(date, endDate, circa) {
  if (!date) return "?";
  const prefix = circa ? "c. " : "";
  const start = date.length > 7 ? date.substring(0, 7) : date;
  if (!endDate) return prefix + start;
  const end = endDate.length > 7 ? endDate.substring(0, 7) : endDate;
  return prefix + start + " – " + end;
}

export function showPersonPanel(personId) {
  const person = S.PEOPLE_MAP[personId];
  if (!person) return;

  const panel = document.getElementById("person-panel");
  const content = document.getElementById("panel-content");

  // Find family connections (with relationship metadata)
  const parentRels = S.DATA.relationships.filter((r) => r.child_id === personId);
  const parents = parentRels.map((r) => r.parent_id);
  const childRels = S.DATA.relationships.filter((r) => r.parent_id === personId);
  const children = childRels.map((r) => r.child_id);
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

  // AI-powered biographical summary
  html += `<div id="panel-summary" class="panel-summary"><div class="panel-summary-loading"><span class="panel-summary-spinner"></span> Generating summary…</div></div>`;

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
  if (person.birth_date || person.birth_place || person.maiden_name || person.has_email) {
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
    if (person.has_email) {
      html += `<div class="panel-detail-item"><span class="panel-detail-icon" style="color:var(--accent)">&#10003;</span><div class="panel-detail-body"><span class="panel-detail-label">App access</span><span class="panel-detail-value">Can sign in</span></div></div>`;
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

  // Separate birth family (biological parents when adoptive parents exist)
  const hasAdoptiveParent = parentRels.some((r) => (r.rel_type || "biological") === "adoptive");
  const birthParentRels = hasAdoptiveParent
    ? parentRels.filter((r) => (r.rel_type || "biological") === "biological")
    : [];
  const familyParentRels = hasAdoptiveParent
    ? parentRels.filter((r) => (r.rel_type || "biological") !== "biological")
    : parentRels;

  function _relTypePill(rel) {
    const t = rel.rel_type || "biological";
    if (t === "biological" && !hasAdoptiveParent) return `<span class="panel-rel-pill panel-rel-parent">parent</span>`;
    const label = t === "biological" ? "birth parent" : t + " parent";
    return `<span class="panel-rel-pill panel-rel-parent">${label}</span>`;
  }

  function _visibilityBadge(rel) {
    const v = rel.visibility;
    if (!v || v === "everyone") return "";
    const label = v === "private" ? "private" : "family only";
    return `<span class="panel-visibility-badge">${label}</span>`;
  }

  // Family
  if (familyParentRels.length || children.length || partners.length || siblings.length) {
    html += `<div class="panel-section"><h3>Family</h3><ul class="panel-family-list">`;
    for (const rel of familyParentRels) {
      html += `<li><a class="person-link" data-person-id="${rel.parent_id}" href="javascript:void(0)">${personThumb(rel.parent_id, 28)} ${personName(rel.parent_id)}</a> ${_relTypePill(rel)}${_visibilityBadge(rel)}</li>`;
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

  // Birth Family (shown separately when person has both biological and adoptive parents)
  if (birthParentRels.length) {
    html += `<div class="panel-section panel-birth-family"><h3>Birth Family</h3><ul class="panel-family-list">`;
    for (const rel of birthParentRels) {
      html += `<li><a class="person-link" data-person-id="${rel.parent_id}" href="javascript:void(0)">${personThumb(rel.parent_id, 28)} ${personName(rel.parent_id)}</a> <span class="panel-rel-pill panel-rel-birth">birth parent</span>${_visibilityBadge(rel)}</li>`;
    }
    html += `</ul></div>`;
  }

  // Invite section (editors only)
  if (!S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor) {
    html += _buildInviteSection(personId, person);
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

  // ── Places & Residences section (residence/immigration/etc. events) ──
  html += _buildPlacesSection(personId, person, events);

  // Life events + dated photos merged into one timeline. Place-type events
  // (residence/immigration/emigration/naturalization) are rendered in the
  // Places section above, so exclude them here.
  const PLACE_EVENT_TYPES = new Set([
    "residence", "immigration", "emigration", "naturalization",
  ]);
  const personPhotos = (S.DATA.photos || []).filter((p) =>
    p.date && (p.tagged_people || []).some((tp) => tp.person_id === personId)
  );
  const canEditEvents = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  const timelineItems = [
    ...events
      .filter((e) => !PLACE_EVENT_TYPES.has(e.event_type))
      .map((e) => ({ kind: "event", date: e.date || "", sortDate: e.date || "9999", ...e })),
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
      const date = e.kind === "photo"
        ? (e.date ? e.date.substring(0, 7) : "?")
        : _formatEventDate(e.date, e.end_date, e.date_circa);
      const icon = e.kind === "photo" ? "📷" : _eventIcon(e.event_type);
      const colorVar = e.kind === "photo" ? "--event-custom" : _eventColorVar(e.event_type);
      const photoThumb = e.kind === "photo" && e.photoPath
        ? `<img class="panel-event-photo" src="/${e.photoPath}" alt="" loading="lazy" onclick="openLightbox('/${e.photoPath}', '${(e.description || "").replace(/'/g, "\\'")}', '${e.photoPath}')" />`
        : "";
      const editActions = (e.kind === "event" && canEditEvents && e.id)
        ? `<span class="panel-event-actions"><button class="panel-event-edit-btn" onclick="openEditEventForm(${e.id}, '${personId}')" title="Edit">✎</button><button class="panel-event-del-btn" onclick="deleteEvent(${e.id}, '${personId}')" title="Delete">×</button></span>`
        : "";
      html += `
        <div class="panel-event">
          <div class="panel-event-marker" style="--marker-color:var(${colorVar})">
            <span class="panel-event-icon">${icon}</span>
            <span class="panel-event-line"></span>
          </div>
          <div class="panel-event-body">
            <span class="panel-event-date">${date}</span>
            <span class="panel-event-desc">${escapeHtml(e.description || (e.kind === "event" ? (_EVENT_TYPE_LABELS[e.event_type] || e.event_type) : ""))}${e.place ? " · <span class='panel-event-place'>" + escapeHtml(e.place) + "</span>" : ""}${e.source && e.source.startsWith("http") ? ` · <a class="panel-event-source" href="${escapeHtml(e.source)}" target="_blank" rel="noopener">source</a>` : ""}</span>
            ${photoThumb}
            ${editActions}
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  // Add event button (editors only)
  if (!S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor) {
    html += `<div class="panel-section">
      <button class="panel-add-event-btn" onclick="openAddEventForm('${personId}')">+ Add Life Event</button>
      <div id="add-event-form" class="add-relative-form hidden"></div>
    </div>`;
  }

  // Notes
  if (person.notes) {
    html += `<div class="panel-section"><h3>Notes</h3><div class="panel-notes">${escapeHtml(person.notes)}</div></div>`;
  }

  content.innerHTML = html;
  const photosSection = content.querySelector(".panel-photos-section");
  if (photosSection) {
    _wireCarousel(photosSection, personId);
    _wirePanelPhotoClicks(photosSection, personId);
  }
  panel.classList.remove("hidden");
  requestAnimationFrame(() => panel.classList.add("panel-open"));
  if (S.MAP) setTimeout(() => S.MAP.invalidateSize(), 250);
  // On the tree, pan the selected node into the visible area if the panel now
  // covers it (or it's off-screen). No-op on other views.
  if (typeof activeViewName === "function" && activeViewName() === "tree") {
    ensureTreeNodeVisible(personId);
  }

  _fetchPersonSummary(personId);
}

function _fetchPersonSummary(personId) {
  const el = document.getElementById("panel-summary");
  if (!el) return;

  fetch(`/api/people/${encodeURIComponent(personId)}/summary`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      if (!data.summary) {
        el.remove();
        return;
      }
      el.innerHTML = `<div class="panel-summary-text">${escapeHtml(data.summary)}</div>`;
    })
    .catch(() => {
      el.remove();
    });
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
        ${relationship === "parent" || relationship === "child" ? `
        <div class="add-relative-row">
          <select id="arf-rel-type" class="add-relative-input">
            <option value="biological">Biological</option>
            <option value="adoptive">Adoptive</option>
            <option value="step">Step</option>
            <option value="foster">Foster</option>
          </select>
          <select id="arf-visibility" class="add-relative-input">
            <option value="everyone">Visible to everyone</option>
            <option value="self_and_children">Family only</option>
            <option value="private">Private</option>
          </select>
        </div>` : ""}
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
        ${relationship === "parent" || relationship === "child" ? `
        <div class="add-relative-row">
          <select id="arf-link-rel-type" class="add-relative-input">
            <option value="biological">Biological</option>
            <option value="adoptive">Adoptive</option>
            <option value="step">Step</option>
            <option value="foster">Foster</option>
          </select>
          <select id="arf-link-visibility" class="add-relative-input">
            <option value="everyone">Visible to everyone</option>
            <option value="self_and_children">Family only</option>
            <option value="private">Private</option>
          </select>
        </div>` : ""}
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
export async function linkRelative(personId, relationship, relativeId, errorEl, opts = {}) {
  const relType = opts.rel_type || "biological";
  const visibility = opts.visibility || "everyone";

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
      relPairs.push({ parent_id: relativeId, child_id: personId, rel_type: relType, visibility });
    } else if (relationship === "child") {
      relPairs.push({ parent_id: personId, child_id: relativeId, rel_type: relType, visibility });
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
  const opts = {};
  const rtEl = document.getElementById("arf-link-rel-type");
  const visEl = document.getElementById("arf-link-visibility");
  if (rtEl) opts.rel_type = rtEl.value;
  if (visEl) opts.visibility = visEl.value;
  await linkRelative(personId, relationship, _arfSelectedPersonId, errorEl, opts);
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

  const opts = {};
  const rtEl = document.getElementById("arf-rel-type");
  const visEl = document.getElementById("arf-visibility");
  if (rtEl) opts.rel_type = rtEl.value;
  if (visEl) opts.visibility = visEl.value;
  await linkRelative(personId, relationship, newPersonId, errorEl, opts);
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
      <div class="add-relative-row">
        <input id="epf-email" type="email" placeholder="Email (optional)" class="add-relative-input" value="${esc(person.email)}" />
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
  const emailVal = document.getElementById("epf-email").value.trim();
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
        email: emailVal || null,
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
// Invite by Email
// ═══════════════════════════════════════════════════════════════

function _buildInviteSection(personId, person) {
  const esc = escapeHtml;
  let inner = "";

  if (person.email) {
    const siteUrl = window.location.origin;
    const firstName = person.given_name || person.surname || "there";
    const inviteMsg = `Hey ${firstName}, I’ve added you to our family tree! Sign in with your Google account (${person.email}) to explore it: ${siteUrl}`;
    inner = `
      <div class="invite-has-email">
        <div class="invite-email-badge">${esc(person.email)}</div>
        <div class="invite-msg-box">
          <div class="invite-msg-text" id="invite-msg-text">${esc(inviteMsg)}</div>
          <button class="invite-copy-btn" onclick="copyInviteMessage('${personId}')">Copy invite message</button>
        </div>
        <div id="invite-copied" class="invite-copied hidden">Copied!</div>
      </div>`;
  } else {
    inner = `
      <div class="invite-no-email">
        <p class="invite-hint">Add a Gmail address so ${esc(person.given_name || person.surname || "this person")} can sign in and explore the family tree.</p>
        <div id="invite-email-form" class="invite-email-form">
          <div class="add-relative-row">
            <input id="invite-email-input" type="email" placeholder="user@gmail.com" class="add-relative-input" />
          </div>
          <div class="add-relative-actions">
            <button class="add-relative-submit" onclick="submitInviteEmail('${personId}')">Set email &amp; get invite link</button>
          </div>
          <div id="invite-error" class="add-relative-error hidden"></div>
        </div>
      </div>`;
  }

  return `<div class="panel-section panel-invite-section"><h3>Invite</h3>${inner}</div>`;
}

export async function submitInviteEmail(personId) {
  const input = document.getElementById("invite-email-input");
  const errorEl = document.getElementById("invite-error");
  if (!input || !errorEl) return;

  const email = input.value.trim().toLowerCase();
  if (!email) {
    errorEl.textContent = "Enter an email address.";
    errorEl.classList.remove("hidden");
    return;
  }
  if (!email.includes("@") || !email.includes(".")) {
    errorEl.textContent = "Enter a valid email address.";
    errorEl.classList.remove("hidden");
    return;
  }

  errorEl.classList.add("hidden");

  try {
    const res = await fetch(`/api/people/${personId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      const data = await res.json();
      errorEl.textContent = data.error || "Failed to set email.";
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

export async function copyInviteMessage(personId) {
  const msgEl = document.getElementById("invite-msg-text");
  const copiedEl = document.getElementById("invite-copied");
  if (!msgEl) return;

  try {
    await navigator.clipboard.writeText(msgEl.textContent);
  } catch {
    const range = document.createRange();
    range.selectNodeContents(msgEl);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand("copy");
    sel.removeAllRanges();
  }

  if (copiedEl) {
    copiedEl.classList.remove("hidden");
    setTimeout(() => copiedEl.classList.add("hidden"), 2000);
  }
}

// ═══════════════════════════════════════════════════════════════
// Places & Residences Section
// ═══════════════════════════════════════════════════════════════

function _buildPlacesSection(personId, person, events) {
  const placeEvents = events.filter(e =>
    e.event_type === "residence" || e.event_type === "immigration" ||
    e.event_type === "emigration" || e.event_type === "naturalization"
  );

  const hasPlaceData = person.birth_place || person.death_place || placeEvents.length > 0;
  if (!hasPlaceData) return "";

  const canEdit = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  let html = `<div class="panel-section"><h3>Places</h3><div class="panel-places-timeline">`;

  // Birth place entry
  if (person.birth_place) {
    html += `
      <div class="panel-place-entry panel-place-birth">
        <div class="panel-place-marker"><span class="panel-place-dot born"></span><span class="panel-place-line"></span></div>
        <div class="panel-place-body">
          <div class="panel-place-name">${escapeHtml(person.birth_place)}</div>
          <div class="panel-place-dates"><span class="panel-place-type-pill birth">Born</span>${person.birth_date ? " " + escapeHtml(person.birth_date) : ""}</div>
        </div>
      </div>`;
  }

  // Residence & migration events
  for (const e of placeEvents) {
    if (!e.place && !e.description) continue;
    const dateStr = _formatEventDate(e.date, e.end_date, e.date_circa);
    const typeLabel = _EVENT_TYPE_LABELS[e.event_type] || e.event_type;
    const typeClass = e.event_type;
    const icon = _eventIcon(e.event_type);
    html += `
      <div class="panel-place-entry">
        <div class="panel-place-marker"><span class="panel-place-dot ${typeClass}">${icon}</span><span class="panel-place-line"></span></div>
        <div class="panel-place-body">
          <div class="panel-place-name">${escapeHtml(e.place || e.description || typeLabel)}</div>
          <div class="panel-place-dates">
            <span class="panel-place-type-pill ${typeClass}">${typeLabel}</span>
            ${dateStr !== "?" ? " " + dateStr : ""}
          </div>
          ${e.description && e.place ? `<div class="panel-place-desc">${escapeHtml(e.description)}</div>` : ""}
          ${canEdit && e.id ? `<span class="panel-event-actions"><button class="panel-event-edit-btn" onclick="openEditEventForm(${e.id}, '${personId}')" title="Edit">✎</button><button class="panel-event-del-btn" onclick="deleteEvent(${e.id}, '${personId}')" title="Delete">×</button></span>` : ""}
        </div>
      </div>`;
  }

  // Death place entry
  if (person.death_place) {
    html += `
      <div class="panel-place-entry panel-place-death">
        <div class="panel-place-marker"><span class="panel-place-dot death">✝</span></div>
        <div class="panel-place-body">
          <div class="panel-place-name">${escapeHtml(person.death_place)}</div>
          <div class="panel-place-dates"><span class="panel-place-type-pill death">Died</span>${person.death_date ? " " + escapeHtml(person.death_date) : ""}</div>
        </div>
      </div>`;
  }

  html += `</div>`;

  // Add place button (editors only)
  if (canEdit) {
    html += `<button class="panel-add-place-btn" onclick="openAddPlaceForm('${personId}')">+ Add Place</button>`;
    html += `<div id="add-place-form" class="add-relative-form hidden"></div>`;
  }
  html += `</div>`;

  return html;
}

// ═══════════════════════════════════════════════════════════════
// Add Place Form
// ═══════════════════════════════════════════════════════════════

export function openAddPlaceForm(personId) {
  const form = document.getElementById("add-place-form");
  if (!form) return;

  form.innerHTML = `
    <div class="add-relative-form-inner">
      <div class="add-relative-row">
        <select id="apf-type" class="add-relative-input">
          <option value="residence">Residence</option>
          <option value="immigration">Immigration</option>
          <option value="emigration">Emigration</option>
          <option value="naturalization">Naturalization</option>
        </select>
      </div>
      <div class="add-relative-row">
        <input id="apf-place" type="text" placeholder="Place (e.g. Boston, MA)" class="add-relative-input" />
      </div>
      <div class="add-relative-row">
        <input id="apf-date" type="text" placeholder="Start date (e.g. 1985 or 1985-03)" class="add-relative-input" />
        <input id="apf-end-date" type="text" placeholder="End date (optional)" class="add-relative-input" />
      </div>
      <div class="add-relative-row">
        <label class="apf-circa-label"><input id="apf-circa" type="checkbox" /> Approximate date</label>
      </div>
      <div class="add-relative-row">
        <input id="apf-desc" type="text" placeholder="Description (optional)" class="add-relative-input" />
      </div>
      <div class="add-relative-actions">
        <button class="add-relative-submit" onclick="submitAddPlace('${personId}')">Add Place</button>
        <button class="add-relative-cancel" onclick="document.getElementById('add-place-form').classList.add('hidden')">Cancel</button>
      </div>
      <div id="apf-error" class="add-relative-error hidden"></div>
    </div>
  `;
  form.classList.remove("hidden");
  document.getElementById("apf-place")?.focus();
}

export async function submitAddPlace(personId) {
  const eventType = document.getElementById("apf-type").value;
  const place = document.getElementById("apf-place").value.trim();
  const date = document.getElementById("apf-date").value.trim();
  const endDate = document.getElementById("apf-end-date").value.trim();
  const circa = document.getElementById("apf-circa").checked;
  const desc = document.getElementById("apf-desc").value.trim();
  const errorEl = document.getElementById("apf-error");

  if (!place && !desc) {
    errorEl.textContent = "Enter at least a place or description.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    const body = { person_id: personId, event_type: eventType };
    if (place) body.place = place;
    if (date) body.date = date;
    if (endDate) body.end_date = endDate;
    if (circa) body.date_circa = true;
    if (desc) body.description = desc;

    const res = await fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json();
      errorEl.textContent = data.error || "Failed to add place.";
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
// Add Life Event Form
// ═══════════════════════════════════════════════════════════════

export function openAddEventForm(personId) {
  const form = document.getElementById("add-event-form");
  if (!form) return;

  form.innerHTML = `
    <div class="add-relative-form-inner">
      <div class="add-relative-row">
        <select id="aef-type" class="add-relative-input">
          <option value="education">Education</option>
          <option value="career">Career</option>
          <option value="military">Military</option>
          <option value="religion">Religion</option>
          <option value="medical">Medical</option>
          <option value="custom">Other</option>
        </select>
      </div>
      <div class="add-relative-row">
        <input id="aef-desc" type="text" placeholder="Description" class="add-relative-input" />
      </div>
      <div class="add-relative-row">
        <input id="aef-date" type="text" placeholder="Start date (e.g. 1985)" class="add-relative-input" />
        <input id="aef-end-date" type="text" placeholder="End date (optional)" class="add-relative-input" />
      </div>
      <div class="add-relative-row">
        <label class="apf-circa-label"><input id="aef-circa" type="checkbox" /> Approximate date</label>
      </div>
      <div class="add-relative-row">
        <input id="aef-place" type="text" placeholder="Place (optional)" class="add-relative-input" />
      </div>
      <div class="add-relative-actions">
        <button class="add-relative-submit" onclick="submitAddEvent('${personId}')">Add Event</button>
        <button class="add-relative-cancel" onclick="document.getElementById('add-event-form').classList.add('hidden')">Cancel</button>
      </div>
      <div id="aef-error" class="add-relative-error hidden"></div>
    </div>
  `;
  form.classList.remove("hidden");
  document.getElementById("aef-desc")?.focus();
}

export async function submitAddEvent(personId) {
  const eventType = document.getElementById("aef-type").value;
  const desc = document.getElementById("aef-desc").value.trim();
  const date = document.getElementById("aef-date").value.trim();
  const endDate = document.getElementById("aef-end-date").value.trim();
  const circa = document.getElementById("aef-circa").checked;
  const place = document.getElementById("aef-place").value.trim();
  const errorEl = document.getElementById("aef-error");

  if (!desc) {
    errorEl.textContent = "Enter a description.";
    errorEl.classList.remove("hidden");
    return;
  }

  try {
    const body = { person_id: personId, event_type: eventType, description: desc };
    if (date) body.date = date;
    if (endDate) body.end_date = endDate;
    if (circa) body.date_circa = true;
    if (place) body.place = place;

    const res = await fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json();
      errorEl.textContent = data.error || "Failed to add event.";
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
// Edit / Delete Event
// ═══════════════════════════════════════════════════════════════

export function openEditEventForm(eventId, personId) {
  const event = (S.DATA.events || []).find(e => e.id === eventId);
  if (!event) return;

  const panel = document.getElementById("panel-content");
  if (!panel) return;

  let container = document.getElementById("edit-event-overlay");
  if (!container) {
    container = document.createElement("div");
    container.id = "edit-event-overlay";
    container.className = "edit-event-overlay";
    panel.appendChild(container);
  }

  const esc = escapeHtml;
  container.innerHTML = `
    <div class="add-relative-form-inner">
      <h3 style="margin:0 0 10px">Edit Event</h3>
      <div class="add-relative-row">
        <select id="eef-type" class="add-relative-input">
          ${Object.entries(_EVENT_TYPE_LABELS).filter(([k]) => k !== "birth" && k !== "death" && k !== "marriage" && k !== "divorce").map(([k, v]) =>
            `<option value="${k}" ${event.event_type === k ? "selected" : ""}>${v}</option>`
          ).join("")}
        </select>
      </div>
      <div class="add-relative-row">
        <input id="eef-place" type="text" placeholder="Place" class="add-relative-input" value="${esc(event.place || "")}" />
      </div>
      <div class="add-relative-row">
        <input id="eef-date" type="text" placeholder="Start date" class="add-relative-input" value="${esc(event.date || "")}" />
        <input id="eef-end-date" type="text" placeholder="End date" class="add-relative-input" value="${esc(event.end_date || "")}" />
      </div>
      <div class="add-relative-row">
        <label class="apf-circa-label"><input id="eef-circa" type="checkbox" ${event.date_circa ? "checked" : ""} /> Approximate date</label>
      </div>
      <div class="add-relative-row">
        <input id="eef-desc" type="text" placeholder="Description" class="add-relative-input" value="${esc(event.description || "")}" />
      </div>
      <div class="add-relative-actions">
        <button class="add-relative-submit" onclick="submitEditEvent(${eventId}, '${personId}')">Save</button>
        <button class="add-relative-cancel" onclick="document.getElementById('edit-event-overlay')?.remove()">Cancel</button>
      </div>
      <div id="eef-error" class="add-relative-error hidden"></div>
    </div>
  `;
  container.classList.remove("hidden");
  document.getElementById("eef-place")?.focus();
}

export async function submitEditEvent(eventId, personId) {
  const eventType = document.getElementById("eef-type").value;
  const place = document.getElementById("eef-place").value.trim();
  const date = document.getElementById("eef-date").value.trim();
  const endDate = document.getElementById("eef-end-date").value.trim();
  const circa = document.getElementById("eef-circa").checked;
  const desc = document.getElementById("eef-desc").value.trim();
  const errorEl = document.getElementById("eef-error");

  try {
    const body = {
      event_type: eventType,
      place: place || null,
      date: date || null,
      end_date: endDate || null,
      date_circa: circa,
      description: desc || null,
    };

    const res = await fetch(`/api/events/${eventId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json();
      errorEl.textContent = data.error || "Failed to save.";
      errorEl.classList.remove("hidden");
      return;
    }
  } catch {
    errorEl.textContent = "Network error.";
    errorEl.classList.remove("hidden");
    return;
  }

  await loadData();
  autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);
  refreshAllViews();
  showPersonPanel(personId);
}

export async function deleteEvent(eventId, personId) {
  if (!confirm("Delete this event?")) return;

  try {
    const res = await fetch(`/api/events/${eventId}`, { method: "DELETE" });
    if (!res.ok) return;
  } catch {
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

