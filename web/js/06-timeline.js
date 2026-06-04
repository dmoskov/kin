// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

let TIMELINE_ALIGNED = localStorage.getItem("timelineAligned") !== "false"; // default: aligned

export function gatherTimelineEntries() {
  let entries = [];

  // Births & Deaths
  for (const p of S.DATA.people) {
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
  for (const e of S.DATA.events) {
    if (e.event_type === "birth" || e.event_type === "death") continue;
    entries.push({
      date: e.date || "",
      year: e.date ? parseInt(e.date.substring(0, 4)) : null,
      type: e.event_type,
      personId: e.person_id,
      title: `${personLink(e.person_id)} — ${escapeHtml(e.description || e.event_type)}`,
      desc: e.description || "",
      place: e.place,
      lane: assignLane(e.person_id),
    });
  }

  // Marriages (assign to first partner's lane, mark cross-lane)
  for (const u of S.DATA.unions) {
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
  if (S.CONFIG?.timelinePhotos !== false && S.DATA.photos) {
    for (const photo of S.DATA.photos) {
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
        title: escapeHtml(caption) || `Photo — ${escapeHtml(dateDisplay)}`,
        desc: photo.place || "",
        place: photo.place,
        lane: personId ? assignLane(personId) : (S.LANES[0]?.id || "all"),
        photoPath: photo.file_path,
        dateDisplay: dateDisplay,
      });
    }
  }

  return entries.filter((e) => e.date && e.year);
}

export function renderTimeline(filterPersonId = "all") {
  const container = document.getElementById("timeline-entries");

  let entries = gatherTimelineEntries();

  // Filter by person
  if (filterPersonId !== "all") {
    entries = entries.filter((e) => e.personId === filterPersonId);
  }

  // Sort chronologically
  entries.sort((a, b) => a.date.localeCompare(b.date));

  if (entries.length === 0) {
    container.innerHTML = `<div class="empty-state">
      <p class="empty-state-title">No dated events yet</p>
      <p class="empty-state-hint">${
        filterPersonId !== "all"
          ? "This person has no dated events. Add birth, death, or marriage dates."
          : "Add birth, death, or marriage dates to people and they'll appear on the timeline."
      }</p>
    </div>`;
    const nav = document.getElementById("decade-nav");
    if (nav) nav.innerHTML = "";
    return;
  }

  // Use configured lanes, or a single fallback lane when none are defined
  const activeLanes = S.LANES.length > 0 ? S.LANES : [{ id: "all", label: "All", color: "var(--accent)" }];

  // Group entries by lane
  const byLane = {};
  for (const lane of activeLanes) byLane[lane.id] = [];
  for (const e of entries) {
    const laneId = S.LANES.length > 0 ? e.lane : "all";
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
  if (S.SHOW_TIMELINE_STREAM) {
    for (const e of entries) {
      const decade = Math.floor(e.year / 10) * 10;
      if (!byDecade[decade]) byDecade[decade] = [];
      byDecade[decade].push(e);
    }
  }

  // Column count: lanes + optional stream column
  const colCount = activeLanes.length + (S.SHOW_TIMELINE_STREAM ? 1 : 0);

  // Decade-row-first layout: each decade is a row spanning all lanes so heights stay aligned
  // When stream is active: stream gets 1/3 width, lanes share remaining 2/3
  const swimLaneCount = activeLanes.length;
  let streamGridCols = "";
  if (S.SHOW_TIMELINE_STREAM) {
    if (swimLaneCount > 0) {
      const streamFr = swimLaneCount / 2;
      const laneCols = Array(swimLaneCount).fill("minmax(180px, 1fr)").join(" ");
      streamGridCols = `${streamFr}fr ${laneCols}`;
    } else {
      streamGridCols = "1fr";
    }
  }
  let html = `<div class="timeline-grid${S.SHOW_TIMELINE_STREAM ? " has-stream" : ""}" style="--lane-count:${colCount}${streamGridCols ? `;--stream-grid:${streamGridCols}` : ""}">`;

  // Sticky header row
  html += `<div class="timeline-row timeline-header-row">`;
  if (S.SHOW_TIMELINE_STREAM) {
    html += `<div class="timeline-cell-header tstream-col-header" style="border-bottom-color:var(--accent)">
      <span class="lane-color-dot" style="background:var(--accent)"></span>
      Stream
      <span class="lane-count">${entries.length}</span>
    </div>`;
  }
  for (const lane of activeLanes) {
    html += `
      <div class="timeline-cell-header" style="border-bottom-color:${lane.color}">
        <span class="lane-color-dot" style="background:${lane.color}"></span>
        ${lane.label}
        <span class="lane-count">${byLane[lane.id].length}</span>
      </div>`;
  }
  html += `</div>`;

  // One row per decade
  for (const decade of decades) {
    html += `<div class="timeline-row" id="decade-row-${decade}">`;
    // Stream column first (left side)
    if (S.SHOW_TIMELINE_STREAM) {
      const streamEntries = byDecade[decade] || [];
      html += `<div class="timeline-cell tstream-cell${streamEntries.length === 0 ? " timeline-cell-empty" : ""}">`;
      html += buildStreamCellHtml(streamEntries);
      html += `</div>`;
    }
    activeLanes.forEach((lane, laneIndex) => {
      const decadeEntries = byLaneDecade[lane.id][decade] || [];
      const isEmpty = decadeEntries.length === 0;
      html += `<div class="timeline-cell${isEmpty ? " timeline-cell-empty" : ""}">`;
      // Decade label only in the first lane — a single left-edge "ruler" rather
      // than the same watermark repeated faintly in every column.
      if (laneIndex === 0) {
        html += `<div class="timeline-decade">${decade}s</div>`;
      }
      for (const e of decadeEntries) {
        const isCross = e.crossLane;
        const isMinimal = (e.type === "birth" || e.type === "death" || e.type === "marriage") && !e.place && !e.desc;
        html += `
          <div class="timeline-entry${isCross ? " timeline-cross-marriage" : ""}${e.type === "photo" ? " timeline-photo-entry" : ""}${isMinimal ? " timeline-entry-minimal" : ""}" data-type="${e.type}" data-year="${e.year}" data-person-id="${e.personId || ""}">
            <div class="timeline-entry-dot" style="border-color:${e.type === "photo" ? (EVENT_COLORS.photo || "#d4a843") : lane.color}"></div>
            <div class="timeline-content">
              <span class="timeline-year-inline">${escapeHtml(e.dateDisplay || e.year)}</span>
              ${e.type === "photo" && e.photoPath ? `<img class="timeline-photo-thumb" src="/${e.photoPath}" alt="" loading="lazy" onclick="openLightbox('/${e.photoPath}', '${(e.title || "").replace(/'/g, "\\'")}', '${e.photoPath}')" />` : ""}
              <h4>${e.title}</h4>
              ${e.place ? `<div class="timeline-place"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:3px"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>${escapeHtml(e.place)}</div>` : ""}
            </div>
          </div>`;
      }
      html += `</div>`;
    });
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

  renderDecadeNav(decades, entries);
}

export function toggleTimelineAlignment() {
  TIMELINE_ALIGNED = !TIMELINE_ALIGNED;
  localStorage.setItem("timelineAligned", TIMELINE_ALIGNED);
  const btn = document.getElementById("timeline-align-toggle");
  if (btn) btn.textContent = TIMELINE_ALIGNED ? "Compact" : "Aligned";
  renderTimeline(document.getElementById("timeline-filter")?.value || "all");
}

export function toggleTimelineView() {
  S.SHOW_TIMELINE_STREAM = !S.SHOW_TIMELINE_STREAM;
  localStorage.setItem("showTimelineStream", S.SHOW_TIMELINE_STREAM);
  const btn = document.getElementById("timeline-view-toggle");
  if (btn) btn.textContent = S.SHOW_TIMELINE_STREAM ? "Hide Stream" : "Stream";
  renderTimeline(document.getElementById("timeline-filter")?.value || "all");
}

export function buildStreamCellHtml(entries) {
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
                <span class="tstream-date">${escapeHtml(e.dateDisplay || e.year)}</span>
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
            <span class="tstream-flat-date">${escapeHtml(e.dateDisplay || e.year)}</span>
            <span class="tstream-flat-title">${e.title}</span>
            ${e.personId ? `<span class="tstream-flat-person">${personLink(e.personId)}</span>` : ""}
          </div>
        </div>`;
    }
  }
  return html;
}

const NAV_TYPE_ICONS = {
  birth: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="5" r="3"/><path d="M3 14c0-2.8 2.2-5 5-5s5 2.2 5 5"/></svg>`,
  death: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>`,
  marriage: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 8a4 4 0 014-4 4 4 0 014 4c0 4-4 7-4 7s-4-3-4-7z"/></svg>`,
  photo: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="12" height="10" rx="1.5"/><circle cx="8" cy="8" r="2.5"/></svg>`,
  immigration: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 8h10m0 0l-3-3m3 3l-3 3"/></svg>`,
};

function renderDecadeNav(decades, entries) {
  const nav = document.getElementById("decade-nav");
  if (!nav) return;

  const byDecade = {};
  let maxCount = 0;
  for (const e of entries) {
    const d = Math.floor(e.year / 10) * 10;
    if (!byDecade[d]) byDecade[d] = [];
    byDecade[d].push(e);
    if (byDecade[d].length > maxCount) maxCount = byDecade[d].length;
  }

  let html = `<div class="decade-nav-label">Decades</div>`;

  for (const decade of decades) {
    const decadeEntries = byDecade[decade] || [];
    const count = decadeEntries.length;
    const barPct = maxCount > 0 ? Math.max(4, Math.round((count / maxCount) * 100)) : 0;

    const typeCounts = {};
    for (const e of decadeEntries) {
      typeCounts[e.type] = (typeCounts[e.type] || 0) + 1;
    }
    const topTypes = Object.entries(typeCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);

    let iconsHtml = "";
    for (const [type] of topTypes) {
      const icon = NAV_TYPE_ICONS[type];
      const color = EVENT_COLORS[type] || EVENT_COLORS.custom || "#b066e0";
      if (icon) {
        iconsHtml += `<span class="decade-nav-icon" style="color:${color}">${icon}</span>`;
      } else {
        iconsHtml += `<span class="decade-nav-dot" style="background:${color}"></span>`;
      }
    }

    html += `
      <button class="decade-nav-item${count === 0 ? " decade-nav-empty" : ""}" data-decade="${decade}" title="${decade}s — ${count} event${count !== 1 ? "s" : ""}">
        <span class="decade-nav-year">${decade}s</span>
        <span class="decade-nav-bar-track">
          <span class="decade-nav-bar" style="width:${count > 0 ? barPct : 0}%"></span>
        </span>
        <span class="decade-nav-icons">${iconsHtml}</span>
      </button>`;
  }

  nav.innerHTML = html;

  if (!nav._hasClickHandler) {
    nav._hasClickHandler = true;
    nav.addEventListener("click", (e) => {
      const btn = e.target.closest(".decade-nav-item");
      if (!btn) return;
      const decade = btn.dataset.decade;
      const row = document.getElementById(`decade-row-${decade}`);
      if (!row) return;
      const scroller = row.closest(".timeline-container");
      if (scroller) {
        const headerOffset = scroller.querySelector(".timeline-header")?.offsetHeight || 0;
        const rowTop = row.offsetTop - scroller.offsetTop - headerOffset - 8;
        scroller.scrollTo({ top: rowTop, behavior: "smooth" });
      }

      nav.querySelectorAll(".decade-nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  }

  observeDecadeScroll(nav, decades);
}

let _decadeObserver = null;
function observeDecadeScroll(nav, decades) {
  if (_decadeObserver) _decadeObserver.disconnect();

  const scroller = document.querySelector(".timeline-container");
  if (!scroller) return;

  _decadeObserver = new IntersectionObserver(
    (observedEntries) => {
      let topDecade = null;
      for (const oe of observedEntries) {
        if (oe.isIntersecting && !topDecade) {
          topDecade = oe.target.id.replace("decade-row-", "");
        }
      }
      if (!topDecade) return;
      nav.querySelectorAll(".decade-nav-item").forEach((b) => {
        b.classList.toggle("active", b.dataset.decade === topDecade);
      });
      const activeBtn = nav.querySelector(".decade-nav-item.active");
      if (activeBtn) activeBtn.scrollIntoView({ block: "nearest", behavior: "smooth" });
    },
    { root: scroller, rootMargin: "-10% 0px -80% 0px", threshold: 0 },
  );

  for (const decade of decades) {
    const row = document.getElementById(`decade-row-${decade}`);
    if (row) _decadeObserver.observe(row);
  }
}

export function populateTimelineFilter() {
  const select = document.getElementById("timeline-filter");
  const sorted = Object.values(S.PEOPLE_MAP).sort((a, b) =>
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


// ── Click a timeline entry to open that person (links/photos keep their own action) ──
document.getElementById("timeline-entries")?.addEventListener("click", (e) => {
  if (e.target.closest("a, img, [onclick]")) return;
  const entry = e.target.closest(".timeline-entry");
  const pid = entry?.dataset.personId;
  if (pid) showPersonPanel(pid);
});
