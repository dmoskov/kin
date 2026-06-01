// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

let TIMELINE_ALIGNED = localStorage.getItem("timelineAligned") !== "false"; // default: aligned
let SHOW_TIMELINE_STREAM = localStorage.getItem("showTimelineStream") !== "false";

function gatherTimelineEntries() {
  let entries = [];

  // Births & Deaths
  for (const p of DATA.people) {
    if (p.birth_date) {
      entries.push({
        date: p.birth_date,
        year: parseInt(p.birth_date.substring(0, 4)),
        type: "birth",
        personId: p.id,
        title: `${personLink(p.id)} born`,
        desc: p.birth_place ? `In ${p.birth_place}` : "",
        place: p.birth_place,
        lane: assignLane(p.id),
      });
    }
    if (p.death_date) {
      entries.push({
        date: p.death_date,
        year: parseInt(p.death_date.substring(0, 4)),
        type: "death",
        personId: p.id,
        title: `${personLink(p.id)} died`,
        desc: p.death_place ? `In ${p.death_place}` : "",
        place: p.death_place,
        lane: assignLane(p.id),
      });
    }
  }

  // Life events
  for (const e of DATA.events) {
    if (e.event_type === "birth" || e.event_type === "death") continue;
    entries.push({
      date: e.date || "",
      year: e.date ? parseInt(e.date.substring(0, 4)) : null,
      type: e.event_type,
      personId: e.person_id,
      title: `${personLink(e.person_id)} — ${e.description || e.event_type}`,
      desc: e.description || "",
      place: e.place,
      lane: assignLane(e.person_id),
    });
  }

  // Marriages (assign to first partner's lane, mark cross-lane)
  for (const u of DATA.unions) {
    if (u.union_date) {
      const lane1 = assignLane(u.partner1_id);
      const lane2 = assignLane(u.partner2_id);
      entries.push({
        date: u.union_date,
        year: parseInt(u.union_date.substring(0, 4)),
        type: "marriage",
        personId: u.partner1_id,
        partner2Id: u.partner2_id,
        title: `${personLink(u.partner1_id)} & ${personLink(u.partner2_id)}`,
        desc: u.notes || "",
        place: u.union_place,
        lane: lane1,
        crossLane: lane1 !== lane2 ? lane2 : null,
      });
    }
  }

  // Photo entries (gated by config)
  if (CONFIG?.timelinePhotos !== false && DATA.photos) {
    for (const photo of DATA.photos) {
      if (!photo.date) continue;
      const year = parseInt(photo.date.substring(0, 4));
      if (!year) continue;
      const primaryPerson = (photo.tagged_people || [])[0];
      const personId = primaryPerson?.person_id;
      const dateDisplay = photo.date_circa ? `c. ${photo.date}` : photo.date;
      const caption = primaryPerson?.caption || "";
      entries.push({
        date: photo.date,
        year: year,
        type: "photo",
        personId: personId || "",
        title: caption || `Photo — ${dateDisplay}`,
        desc: photo.place || "",
        place: photo.place,
        lane: personId ? assignLane(personId) : (LANES[0]?.id || "all"),
        photoPath: photo.file_path,
        dateDisplay: dateDisplay,
      });
    }
  }

  return entries.filter((e) => e.date && e.year);
}

function renderTimeline(filterPersonId = "all") {
  const container = document.getElementById("timeline-entries");

  let entries = gatherTimelineEntries();

  // Filter by person
  if (filterPersonId !== "all") {
    entries = entries.filter((e) => e.personId === filterPersonId);
  }

  // Sort chronologically
  entries.sort((a, b) => a.date.localeCompare(b.date));

  // Use configured lanes, or a single fallback lane when none are defined
  const activeLanes = LANES.length > 0 ? LANES : [{ id: "all", label: "All", color: "var(--accent)" }];

  // Group entries by lane
  const byLane = {};
  for (const lane of activeLanes) byLane[lane.id] = [];
  for (const e of entries) {
    const laneId = LANES.length > 0 ? e.lane : "all";
    if (laneId && byLane[laneId]) byLane[laneId].push(e);
  }

  // Build decade lists: full continuous range for aligned, events-only for compact
  const eventDecades = [...new Set(entries.map((e) => Math.floor(e.year / 10) * 10))].sort();
  let fullDecades = eventDecades;
  if (eventDecades.length > 1) {
    fullDecades = [];
    const min = eventDecades[0];
    const max = eventDecades[eventDecades.length - 1];
    for (let d = min; d <= max; d += 10) fullDecades.push(d);
  }
  const decades = TIMELINE_ALIGNED ? fullDecades : eventDecades;

  // Index entries by lane then decade for O(1) lookup
  const byLaneDecade = {};
  for (const lane of activeLanes) {
    byLaneDecade[lane.id] = {};
    for (const e of byLane[lane.id]) {
      const decade = Math.floor(e.year / 10) * 10;
      if (!byLaneDecade[lane.id][decade]) byLaneDecade[lane.id][decade] = [];
      byLaneDecade[lane.id][decade].push(e);
    }
  }

  // Index entries by decade for the stream column
  const byDecade = {};
  if (SHOW_TIMELINE_STREAM) {
    for (const e of entries) {
      const decade = Math.floor(e.year / 10) * 10;
      if (!byDecade[decade]) byDecade[decade] = [];
      byDecade[decade].push(e);
    }
  }

  // Column count: lanes + optional stream column
  const colCount = activeLanes.length + (SHOW_TIMELINE_STREAM ? 1 : 0);

  // Decade-row-first layout: each decade is a row spanning all lanes so heights stay aligned
  let html = `<div class="timeline-grid${SHOW_TIMELINE_STREAM ? " has-stream" : ""}" style="--lane-count:${colCount}">`;

  // Sticky header row
  html += `<div class="timeline-row timeline-header-row">`;
  for (const lane of activeLanes) {
    html += `
      <div class="timeline-cell-header" style="border-bottom-color:${lane.color}">
        <span class="lane-color-dot" style="background:${lane.color}"></span>
        ${lane.label}
        <span class="lane-count">${byLane[lane.id].length}</span>
      </div>`;
  }
  if (SHOW_TIMELINE_STREAM) {
    html += `<div class="timeline-cell-header tstream-col-header" style="border-bottom-color:var(--accent)">
      <span class="lane-color-dot" style="background:var(--accent)"></span>
      Stream
      <span class="lane-count">${entries.length}</span>
    </div>`;
  }
  html += `</div>`;

  // One row per decade
  for (const decade of decades) {
    html += `<div class="timeline-row">`;
    for (const lane of activeLanes) {
      const decadeEntries = byLaneDecade[lane.id][decade] || [];
      const isEmpty = decadeEntries.length === 0;
      html += `<div class="timeline-cell${isEmpty ? " timeline-cell-empty" : ""}">`;
      html += `<div class="timeline-decade${isEmpty ? " timeline-decade-empty" : ""}">${decade}s</div>`;
      for (const e of decadeEntries) {
        const isCross = e.crossLane;
        html += `
          <div class="timeline-entry${isCross ? " timeline-cross-marriage" : ""}${e.type === "photo" ? " timeline-photo-entry" : ""}" data-type="${e.type}" data-year="${e.year}">
            <div class="timeline-entry-dot" style="border-color:${e.type === "photo" ? (EVENT_COLORS.photo || "#d4a843") : lane.color}"></div>
            <div class="timeline-content">
              <span class="timeline-year-inline">${e.dateDisplay || e.year}</span>
              ${e.type === "photo" && e.photoPath ? `<img class="timeline-photo-thumb" src="/${e.photoPath}" alt="" loading="lazy" onclick="openLightbox('/${e.photoPath}', '${(e.title || "").replace(/'/g, "\\'")}', '${e.photoPath}')" />` : ""}
              <h4>${e.title}</h4>
              ${e.place ? `<div class="timeline-place"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:3px"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>${e.place}</div>` : ""}
            </div>
          </div>`;
      }
      html += `</div>`;
    }
    // Stream column for this decade (no decade label — the lane columns already show it)
    if (SHOW_TIMELINE_STREAM) {
      const streamEntries = byDecade[decade] || [];
      html += `<div class="timeline-cell tstream-cell${streamEntries.length === 0 ? " timeline-cell-empty" : ""}">`;
      html += buildStreamCellHtml(streamEntries);
      html += `</div>`;
    }
    html += `</div>`;
  }

  html += `</div>`;
  container.innerHTML = html;

  // Wire person-link clicks within timeline
  container.querySelectorAll(".person-link").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      showPersonPanel(a.dataset.personId);
    });
  });
}

function toggleTimelineAlignment() {
  TIMELINE_ALIGNED = !TIMELINE_ALIGNED;
  localStorage.setItem("timelineAligned", TIMELINE_ALIGNED);
  const btn = document.getElementById("timeline-align-toggle");
  if (btn) btn.textContent = TIMELINE_ALIGNED ? "Compact" : "Aligned";
  renderTimeline(document.getElementById("timeline-filter")?.value || "all");
}

function toggleTimelineView() {
  SHOW_TIMELINE_STREAM = !SHOW_TIMELINE_STREAM;
  localStorage.setItem("showTimelineStream", SHOW_TIMELINE_STREAM);
  const btn = document.getElementById("timeline-view-toggle");
  if (btn) btn.textContent = SHOW_TIMELINE_STREAM ? "Hide Stream" : "Stream";
  renderTimeline(document.getElementById("timeline-filter")?.value || "all");
}

function buildStreamCellHtml(entries) {
  let html = "";
  for (const e of entries) {
    const color = e.type === "photo"
      ? (EVENT_COLORS.photo || "#d4a843")
      : (EVENT_COLORS[e.type] || EVENT_COLORS.custom || "#b066e0");

    if (e.type === "photo" && e.photoPath) {
      html += `
        <div class="tstream-entry tstream-photo-entry">
          <div class="tstream-rail"><div class="tstream-dot" style="border-color:${color}"></div></div>
          <div class="tstream-card tstream-photo-card">
            <div class="tstream-photo-frame">
              <img class="tstream-photo-img" src="/${e.photoPath}" alt="" loading="lazy"
                   onclick="openLightbox('/${e.photoPath}', '${(e.title || "").replace(/'/g, "\\'")}', '${e.photoPath}')" />
            </div>
            <div class="tstream-card-body">
              <div class="tstream-meta">
                ${e.personId ? personThumb(e.personId, 22) : ""}
                <span class="tstream-date">${e.dateDisplay || e.year}</span>
              </div>
              ${e.title ? `<div class="tstream-title">${e.title}</div>` : ""}
            </div>
          </div>
        </div>`;
    } else {
      html += `
        <div class="tstream-entry tstream-event-flat">
          <div class="tstream-flat-dot" style="background:${color}"></div>
          <div class="tstream-flat-body">
            ${e.personId ? personThumb(e.personId, 20) : ""}
            <span class="tstream-flat-date">${e.dateDisplay || e.year}</span>
            <span class="tstream-flat-title">${e.title}</span>
            ${e.personId ? `<span class="tstream-flat-person">${personLink(e.personId)}</span>` : ""}
          </div>
        </div>`;
    }
  }
  return html;
}

function populateTimelineFilter() {
  const select = document.getElementById("timeline-filter");
  const sorted = Object.values(PEOPLE_MAP).sort((a, b) =>
    a.fullName.localeCompare(b.fullName)
  );
  for (const p of sorted) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.fullName;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => renderTimeline(select.value));
}

// ═══════════════════════════════════════════════════════════════
// Relationship Calculator
// ═══════════════════════════════════════════════════════════════

