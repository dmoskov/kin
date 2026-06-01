// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

function showPersonPanel(personId) {
  const person = PEOPLE_MAP[personId];
  if (!person) return;

  const panel = document.getElementById("person-panel");
  const content = document.getElementById("panel-content");

  // Find family connections
  const parents = DATA.relationships
    .filter((r) => r.child_id === personId)
    .map((r) => r.parent_id);
  const children = DATA.relationships
    .filter((r) => r.parent_id === personId)
    .map((r) => r.child_id);
  const partners = DATA.unions
    .filter((u) => u.partner1_id === personId || u.partner2_id === personId)
    .map((u) => (u.partner1_id === personId ? u.partner2_id : u.partner1_id));
  const events = DATA.events
    .filter((e) => e.person_id === personId)
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  // Show viewer-relative relationship if a viewer is set and this isn't the viewer
  let relBadge = "";
  if (CENTER_ID_A && personId !== CENTER_ID_A) {
    const relLabel = calculateRelationship(CENTER_ID_A, personId);
    if (relLabel && relLabel !== "no relation found") {
      relBadge = `<div class="panel-rel-badge">Your ${relLabel}</div>`;
    }
  }

  let html = `
    <div class="panel-name">${person.fullName}</div>
    ${relBadge}
    <span class="panel-gender ${person.gender}">${person.gender}</span>
    ${!CONFIG?.editorsEnabled || AUTH_USER?.is_editor ? `<button class="panel-edit-btn" onclick="openEditPersonForm('${personId}')">Edit</button>` : ""}
    <div id="edit-person-form" class="add-relative-form hidden"></div>
  `;

  // Photos + Manage Photos button. The inner markup is shared with
  // _renderPanelPhotos (the picker-refresh path) via buildPanelPhotosInnerHtml.
  html += `<div class="panel-photos-section">`;
  html += buildPanelPhotosInnerHtml(personId);
  html += `</div>`;

  // Heritage badge for panel
  const panelHeritage = matchHeritage(person.birth_place);
  if (panelHeritage && CONFIG?.heritageLabels !== false) {
    html += `<span class="panel-heritage-badge" style="color:${panelHeritage.color};border:1px solid ${panelHeritage.color}40;margin-top:8px">${panelHeritage.region}</span>`;
  }

  // Vital stats
  if (person.birth_date || person.birth_place || person.maiden_name) {
    html += `<div class="panel-section"><h3>Details</h3>`;
    if (person.birth_date) {
      html += `<div class="panel-row"><span class="label">Born</span><span>${person.birth_date}${person.birth_place ? " in " + person.birth_place : ""}</span></div>`;
    }
    if (person.death_date) {
      html += `<div class="panel-row"><span class="label">Died</span><span>${person.death_date}${person.death_place ? " in " + person.death_place : ""}</span></div>`;
    }
    if (person.maiden_name) {
      html += `<div class="panel-row"><span class="label">Maiden name</span><span>${person.maiden_name}</span></div>`;
    }
    if (person.email) {
      html += `<div class="panel-row"><span class="label">Email</span><span>${person.email}</span></div>`;
    }
    html += `</div>`;
  }

  // Family
  if (parents.length || children.length || partners.length) {
    const prefix = personRoutePrefix();
    html += `<div class="panel-section"><h3>Family</h3><ul class="panel-family-list">`;
    for (const pid of parents) {
      html += `<li><a class="person-link" data-person-id="${pid}" href="javascript:void(0)">${personThumb(pid, 24)} ${personName(pid)}</a> <span class="label">(parent)</span></li>`;
    }
    for (const pid of partners) {
      html += `<li><a class="person-link" data-person-id="${pid}" href="javascript:void(0)">${personThumb(pid, 24)} ${personName(pid)}</a> <span class="label">(partner)</span></li>`;
    }
    for (const cid of children) {
      html += `<li><a class="person-link" data-person-id="${cid}" href="javascript:void(0)">${personThumb(cid, 24)} ${personName(cid)}</a> <span class="label">(child)</span></li>`;
    }
    html += `</ul></div>`;
  }

  // Add relative buttons (editors only)
  if (!CONFIG?.editorsEnabled || AUTH_USER?.is_editor) {
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

  // Life events
  if (events.length) {
    html += `<div class="panel-section"><h3>Life Events</h3>`;
    for (const e of events) {
      const date = e.date ? e.date.substring(0, 7) : "?";
      html += `
        <div class="panel-event">
          <span class="panel-event-date">${date}</span>
          <span class="panel-event-desc">${e.description || e.event_type}${e.place ? "<br><small>" + e.place + "</small>" : ""}</span>
        </div>`;
    }
    html += `</div>`;
  }

  // Notes
  if (person.notes) {
    html += `<div class="panel-section"><h3>Notes</h3><div class="panel-notes">${person.notes}</div></div>`;
  }

  content.innerHTML = html;
  panel.classList.remove("hidden");
  if (MAP) setTimeout(() => MAP.invalidateSize(), 250);
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

function openAddRelativeForm(personId, relationship) {
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

function switchAddRelativeMode(personId, relationship, mode) {
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

function _getLinkExcludeIds(personId, relationship) {
  const exclude = new Set([personId]);
  if (relationship === "parent") {
    DATA.relationships.filter(r => r.child_id === personId).forEach(r => exclude.add(r.parent_id));
  } else if (relationship === "child") {
    DATA.relationships.filter(r => r.parent_id === personId).forEach(r => exclude.add(r.child_id));
  } else if (relationship === "sibling") {
    const parentIds = DATA.relationships.filter(r => r.child_id === personId).map(r => r.parent_id);
    for (const pid of parentIds) {
      DATA.relationships.filter(r => r.parent_id === pid).forEach(r => exclude.add(r.child_id));
    }
  } else if (relationship === "partner") {
    DATA.unions.filter(u => u.partner1_id === personId || u.partner2_id === personId)
      .forEach(u => { exclude.add(u.partner1_id); exclude.add(u.partner2_id); });
  }
  return exclude;
}

function filterLinkCandidates(personId, relationship) {
  const input = document.getElementById("arf-search");
  const resultsEl = document.getElementById("arf-search-results");
  if (!input || !resultsEl) return;

  const q = input.value.trim().toLowerCase();
  if (!q) { resultsEl.classList.add("hidden"); return; }

  const exclude = _getLinkExcludeIds(personId, relationship);
  const matches = DATA.people.filter(p => {
    if (exclude.has(p.id)) return false;
    const full = ((p.given_name || "") + " " + (p.surname || "")).toLowerCase();
    return full.includes(q);
  }).slice(0, 10);

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

function selectLinkPerson(selectedId, personId, relationship) {
  _arfSelectedPersonId = selectedId;
  const resultsEl = document.getElementById("arf-search-results");
  if (resultsEl) resultsEl.classList.add("hidden");
  const input = document.getElementById("arf-search");
  if (input) input.value = "";

  const selEl = document.getElementById("arf-selected-person");
  if (selEl) {
    const p = PEOPLE_MAP[selectedId];
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

function clearLinkSelection(personId, relationship) {
  _arfSelectedPersonId = null;
  const selEl = document.getElementById("arf-selected-person");
  if (selEl) { selEl.classList.add("hidden"); selEl.innerHTML = ""; }
  const btn = document.getElementById("arf-link-submit");
  if (btn) btn.disabled = true;
  document.getElementById("arf-search")?.focus();
}

async function submitLinkExisting(personId, relationship) {
  const errorEl = document.getElementById("arf-error");
  if (!_arfSelectedPersonId) {
    if (errorEl) { errorEl.textContent = "Select a person first."; errorEl.classList.remove("hidden"); }
    return;
  }

  const linkedId = _arfSelectedPersonId;

  if (relationship === "partner") {
    try {
      const res = await fetch("/api/unions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ partner1_id: personId, partner2_id: linkedId }),
      });
      if (!res.ok) {
        const data = await res.json();
        if (errorEl) { errorEl.textContent = data.error || "Failed to create union."; errorEl.classList.remove("hidden"); }
        return;
      }
    } catch {
      if (errorEl) { errorEl.textContent = "Network error creating union."; errorEl.classList.remove("hidden"); }
      return;
    }
  } else {
    const relPairs = [];
    if (relationship === "parent") {
      relPairs.push({ parent_id: linkedId, child_id: personId });
    } else if (relationship === "child") {
      relPairs.push({ parent_id: personId, child_id: linkedId });
    } else if (relationship === "sibling") {
      const parents = DATA.relationships
        .filter((r) => r.child_id === personId)
        .map((r) => r.parent_id);
      for (const pid of parents) {
        relPairs.push({ parent_id: pid, child_id: linkedId });
      }
      if (relPairs.length === 0) {
        if (errorEl) { errorEl.textContent = "Cannot link sibling: this person has no parents. Add a parent first."; errorEl.classList.remove("hidden"); }
        return;
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
          if (errorEl) { errorEl.textContent = data.error || "Failed to create relationship."; errorEl.classList.remove("hidden"); }
          return;
        }
      }
    } catch {
      if (errorEl) { errorEl.textContent = "Network error creating relationship."; errorEl.classList.remove("hidden"); }
      return;
    }
  }

  await loadData();
  autoComputeLanes(CENTER_ID_A, CENTER_ID_B);
  refreshAllViews();
  showPersonPanel(personId);
}

async function submitAddRelative(personId, relationship) {
  const givenName = document.getElementById("arf-given").value.trim();
  const surname = document.getElementById("arf-surname").value.trim();
  const gender = document.getElementById("arf-gender").value;
  const birthYear = document.getElementById("arf-birth").value.trim();
  const deathYear = document.getElementById("arf-death").value.trim();
  const errorEl = document.getElementById("arf-error");

  if (!givenName && !surname) {
    errorEl.textContent = "Enter at least a first or last name.";
    errorEl.classList.remove("hidden");
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
      errorEl.textContent = data.error || "Failed to create person.";
      errorEl.classList.remove("hidden");
      return;
    }
    newPersonId = data.id;
  } catch {
    errorEl.textContent = "Network error. Please try again.";
    errorEl.classList.remove("hidden");
    return;
  }

  // Build the relationship(s)
  if (relationship === "partner") {
    try {
      const res = await fetch("/api/unions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ partner1_id: personId, partner2_id: newPersonId }),
      });
      if (!res.ok) {
        const data = await res.json();
        errorEl.textContent = data.error || "Failed to create union.";
        errorEl.classList.remove("hidden");
        return;
      }
    } catch {
      errorEl.textContent = "Network error creating union.";
      errorEl.classList.remove("hidden");
      return;
    }
  } else {
    const relPairs = [];
    if (relationship === "parent") {
      relPairs.push({ parent_id: newPersonId, child_id: personId });
    } else if (relationship === "child") {
      relPairs.push({ parent_id: personId, child_id: newPersonId });
    } else if (relationship === "sibling") {
      const parents = DATA.relationships
        .filter((r) => r.child_id === personId)
        .map((r) => r.parent_id);
      for (const pid of parents) {
        relPairs.push({ parent_id: pid, child_id: newPersonId });
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
          errorEl.textContent = data.error || "Failed to create relationship.";
          errorEl.classList.remove("hidden");
          return;
        }
      }
    } catch {
      errorEl.textContent = "Network error creating relationship.";
      errorEl.classList.remove("hidden");
      return;
    }
  }

  // Reload tree data and refresh all views
  await loadData();
  autoComputeLanes(CENTER_ID_A, CENTER_ID_B);
  refreshAllViews();
  showPersonPanel(personId);
}

// ═══════════════════════════════════════════════════════════════
// Edit Person Form
// ═══════════════════════════════════════════════════════════════

function openEditPersonForm(personId) {
  const form = document.getElementById("edit-person-form");
  if (!form) return;

  const person = PEOPLE_MAP[personId];
  if (!person) return;

  const esc = (v) => (v || "").replace(/'/g, "&#39;");

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

async function submitEditPerson(personId) {
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
  autoComputeLanes(CENTER_ID_A, CENTER_ID_B);
  refreshAllViews();
  showPersonPanel(personId);
}

// ═══════════════════════════════════════════════════════════════
// Timeline View
// ═══════════════════════════════════════════════════════════════

