// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

let TIMELINE_ALIGNED = localStorage.getItem("timelineAligned") !== "false"; // default: aligned
let TIMELINE_MODE = localStorage.getItem("timelineMode") || "stream"; // "stream" | "branches"

// Stream rhythm config: which event types get a richer "milestone" card vs the
// quiet default .tstream-event-flat row. Keyed by entry.type; any type NOT here
// (career/education/residence/custom/military/religion/medical/immigration/…)
// stays routine/flat so the feed has a deliberate visual cadence.
const STREAM_TREATMENTS = {
  birth:    { tier: "milestone", variant: "birth" },
  death:    { tier: "milestone", variant: "death" },
  marriage: { tier: "milestone", variant: "marriage" },
};

// Historical-context inserts woven into the stream. Only eras overlapping the
// family's own span are shown; `war` eras additionally list family members with
// military service in that window. Add rows to extend coverage for any family.
// `places`, when present, region-gates an era to families that actually have
// events in that geography — so an Irish family won't see Russian pogroms and a
// family with no Eastern-European roots won't see the Holocaust insert. Eras
// without `places` are universal (world wars, pandemics).
const HISTORICAL_ERAS = [
  { label: "American Revolution", start: 1775, end: 1783, icon: "🇺🇸", war: true,
    places: ["maine", "massachusetts", "newbury", "boston", "virginia", "new york", "connecticut"] },
  { label: "American Civil War", start: 1861, end: 1865, icon: "⚔️", war: true,
    places: ["massachusetts", "maine", "boston", "new york", "virginia"] },
  { label: "Anti-Jewish pogroms in the Russian Empire", start: 1881, end: 1884, icon: "✡️",
    places: ["odessa", "russia", "ukraine", "kishinev", "kamenets", "brody", "poland"] },
  { label: "Romanian Jews denied citizenship", start: 1878, end: 1910, icon: "✡️",
    places: ["romania", "kostence", "constanța", "constanta"] },
  { label: "The Great Wave of immigration (Ellis Island era)", start: 1892, end: 1924, icon: "🚢" },
  { label: "World War I", start: 1914, end: 1918, icon: "🎖️", war: true },
  { label: "The 1918 influenza pandemic", start: 1918, end: 1920, icon: "🦠" },
  { label: "Russian Revolution & Civil War", start: 1917, end: 1922, icon: "🏛️",
    places: ["odessa", "russia", "ukraine"] },
  { label: "Founding of the Republic of Turkey", start: 1923, end: 1938, icon: "🇹🇷",
    places: ["turkey", "istanbul", "constantinople"] },
  { label: "The Great Depression", start: 1929, end: 1939, icon: "📉" },
  { label: "World War II", start: 1939, end: 1945, icon: "🌍", war: true },
  { label: "The Holocaust", start: 1941, end: 1945, icon: "✡️",
    places: ["odessa", "russia", "poland", "romania", "ukraine", "germany", "hungary", "austria", "kamenets", "brody"] },
  { label: "Korean War", start: 1950, end: 1953, icon: "🎖️", war: true },
  { label: "Vietnam War", start: 1955, end: 1975, icon: "🎖️", war: true },
  { label: "COVID-19 pandemic", start: 2020, end: 2022, icon: "🦠" },
];
function eraMidDecade(e) { return Math.floor(((e.start + e.end) / 2) / 10) * 10; }

// Per-branch back-stories: a short note on a significant origin place, shown
// when that branch first appears in the timeline. Matched (and so gated) by
// place keywords against family geography, so each only surfaces for families
// actually from there. Phrased as place facts so they read true for any family.
const PLACE_BACKSTORIES = [
  { match: ["odessa"], icon: "⚓", title: "Odessa",
    text: "A cosmopolitan Black Sea port and home to one of the largest Jewish communities in the Russian Empire — until the pogroms of the 1880s and 1900s drove mass emigration." },
  { match: ["romania", "kostence", "constanța", "constanta"], icon: "🏰", title: "Romania",
    text: "Romania's 1866 constitution denied citizenship to its Jews, leaving them legally stateless and pushing successive waves of emigration." },
  { match: ["istanbul", "constantinople", "turkey"], icon: "🕌", title: "Istanbul",
    text: "Atatürk's 1933 university reform drew 70+ German-Jewish refugee professors to Istanbul, building a Western-standard medical school that trained a generation of physicians." },
  { match: ["iceland"], icon: "🌋", title: "Iceland",
    text: "Harsh winters, volcanic eruptions, and economic hardship in the late 1800s spurred thousands of Icelanders to emigrate to the Upper Midwest." },
  { match: ["kamenets", "podolsk", "brody"], icon: "🏘️", title: "The Podolia shtetls",
    text: "Towns like Kamenets-Podolsky and the border crossing at Brody were waypoints for Jewish families leaving the Pale of Settlement for Hamburg and the Atlantic." },
  { match: ["north end", "salem street", "boston"], icon: "🦞", title: "Boston's North End",
    text: "The North End and Salem Street were the heart of Jewish immigrant commercial life in turn-of-the-century Boston." },
];

// Anchor each matching back-story to the decade its branch first appears (by
// event place OR the person's birthplace), so it introduces the branch in time.
function computeBackstoryAnchors(entries, placesText) {
  const anchors = {};
  const birthById = {};
  for (const p of S.DATA.people) birthById[p.id] = (p.birth_place || "").toLowerCase();
  for (const b of PLACE_BACKSTORIES) {
    if (!b.match.some((k) => placesText.includes(k))) continue;
    let minYear = null;
    for (const e of entries) {
      if (!e.year) continue;
      const hay = ((e.place || "") + " " + (birthById[e.personId] || "")).toLowerCase();
      if (b.match.some((k) => hay.includes(k)) && (minYear === null || e.year < minYear)) minYear = e.year;
    }
    if (minYear === null) continue;
    const d = Math.floor(minYear / 10) * 10;
    (anchors[d] || (anchors[d] = [])).push(b);
  }
  return anchors;
}
function buildBackstoryHtml(b) {
  return `<div class="tstream-backstory"><span class="tstream-backstory-icon">${b.icon}</span>` +
    `<div class="tstream-backstory-body"><div class="tstream-backstory-title">${escapeHtml(b.title)}</div>` +
    `<div class="tstream-backstory-text">${escapeHtml(b.text)}</div></div></div>`;
}

// Era bands for one decade (anchored by the era's midpoint decade), gated to the
// family's year span. War eras list members who served during the window.
function buildEraInserts(decade, minYear, maxYear, military, placesText) {
  const eras = HISTORICAL_ERAS.filter(
    (e) => eraMidDecade(e) === decade && e.end >= minYear && e.start <= maxYear &&
      (!e.places || e.places.some((k) => placesText.includes(k)))
  );
  if (!eras.length) return "";
  return eras.map((e) => {
    let served = "";
    if (e.war) {
      const ids = [...new Set(military.filter((m) => m.year >= e.start && m.year <= e.end).map((m) => m.pid))];
      if (ids.length) served = `<div class="tstream-era-served">🎖️ ${ids.map((id) => personLink(id)).join(", ")}</div>`;
    }
    return `<div class="tstream-era-insert">` +
      `<span class="tstream-era-icon">${e.icon}</span>` +
      `<div class="tstream-era-body"><div class="tstream-era-title">${escapeHtml(e.label)} ` +
      `<span class="tstream-era-years">${e.start}–${e.end}</span></div>${served}</div></div>`;
  }).join("");
}

// Humanize a life-event type slug for empty-description fallbacks so titles
// never read like "Name — career" with a bare lowercase slug.
const EVENT_TYPE_LABELS = {
  career: "Career",
  education: "Education",
  residence: "Residence",
  military: "Military service",
  religion: "Religious milestone",
  medical: "Medical event",
  immigration: "Immigration",
  emigration: "Emigration",
  naturalization: "Naturalization",
  custom: "Life event",
};
function humanizeEventType(slug) {
  if (!slug) return "Life event";
  if (EVENT_TYPE_LABELS[slug]) return EVENT_TYPE_LABELS[slug];
  return slug.charAt(0).toUpperCase() + slug.slice(1);
}

// Document-provenance notes (e.g. a 2020 correction letter about a 19th-c.
// ancestor) are dated by when the document was written, not by a life event, so
// they pollute recent decades. Keep them out of the chronological timeline.
function isArchivalNote(e) {
  const t = e.event_type;
  if (t !== "custom" && t !== "other" && t !== "note") return false;
  const d = (e.description || "").toLowerCase();
  return /\baddendum\b/.test(d) || /requesting corrections?/.test(d) ||
    /\bcorrespondence\b/.test(d) || /addressed to ['"]/.test(d);
}
let LANE_FOCUS = null;            // currently highlighted lane id in stream mode (single-select)
let _decadeObserver = null;       // IntersectionObserver for decade nav; recreated per render

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
    if (isArchivalNote(e)) continue;
    entries.push({
      date: e.date || "",
      year: e.date ? parseInt(e.date.substring(0, 4)) : null,
      type: e.event_type,
      personId: e.person_id,
      title: `${personLink(e.person_id)} — ${escapeHtml(e.description || humanizeEventType(e.event_type))}`,
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
        rawCaption: caption,
        desc: photo.place || "",
        place: photo.place,
        lane: personId ? assignLane(personId) : (S.LANES[0]?.id || "all"),
        photoPath: photo.file_path,
        dateDisplay: dateDisplay,
        // Stash full-photo facts for downstream card rendering / clustering.
        // No image dims are stored anywhere — aspect is measured at load time.
        photoType: photo.photo_type || "photo",
        faceRegions: photo.face_regions || [],
      });
    }
  }

  return clusterPhotoEntries(entries).filter((e) => e.date && e.year);
}

// ── Photo clustering (same-event grouping with collage safety) ───
// Groups multiple photo entries that share a lane + date + place into a
// single cluster card so a burst of shots from one event reads as one unit.
// Non-photo entries pass through untouched. Group key intentionally EXCLUDES
// tagged people (too many photos are untagged) and lane is part of the key so
// cross-lane clustering never happens.
//
// COLLAGE SAFETY: there is no "is a collage" flag and no stored dimensions, so
// a member is treated as "do-not-tile" when it is a group shot, has many faces,
// or (once its runtime aspect is known) is an extreme panorama/strip. Rendering
// is hero+filmstrip (one full-size hero + small thumbs), which guarantees an
// image that is itself already a collage is never shrunk into a tiny tile.
function clusterPhotoEntries(entries) {
  const photos = [];
  const others = [];
  for (const e of entries) {
    if (e.type === "photo" && e.photoPath) photos.push(e);
    else others.push(e);
  }
  if (photos.length === 0) return entries;

  const groups = new Map();
  for (const e of photos) {
    const key = `${e.lane}|${e.date}|${e.place || ""}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  }

  const result = others.slice();
  for (const members of groups.values()) {
    if (members.length === 1) {
      result.push(members[0]);
      continue;
    }
    // Pick a hero: prefer a member that is NOT do-not-tile (group / many faces)
    // so the lead tile is a "normal" photo when possible.
    const isDoNotTile = (m) =>
      m.photoType === "group" || (m.faceRegions || []).length >= 5;
    const hero = members.find((m) => !isDoNotTile(m)) || members[0];
    const rest = members.filter((m) => m !== hero);
    const heroCaption = hero.rawCaption || "";
    const allPaths = members.map((m) => m.photoPath);
    result.push({
      ...hero,
      cluster: true,
      members,
      clusterRest: rest,
      clusterPaths: allPaths,
      title: heroCaption
        ? escapeHtml(heroCaption)
        : `${members.length} photos — ${escapeHtml(hero.place || hero.dateDisplay || hero.year)}`,
    });
  }

  return result;
}

// Entry point. `mode` selects the renderer; defaults to the persisted mode
// ("stream" by default). The full-width chronological feed is the default;
// the swim-lane "branches" grid is an opt-in lens.
export function renderTimeline(filterPersonId = "all", mode = TIMELINE_MODE) {
  TIMELINE_MODE = mode;
  _syncTimelineControls();

  const container = document.getElementById("timeline-entries");
  if (!container) return;

  let entries = gatherTimelineEntries();

  // Filter by person (applies to both modes)
  if (filterPersonId !== "all") {
    entries = entries.filter((e) => e.personId === filterPersonId);
  }

  // Sort chronologically
  entries.sort((a, b) => a.date.localeCompare(b.date));

  if (entries.length === 0) {
    // Tear down any stale decade observer before replacing the DOM
    if (_decadeObserver) { _decadeObserver.disconnect(); _decadeObserver = null; }
    container.innerHTML = `<div class="empty-state">
      <p class="empty-state-title">No dated events yet</p>
      <p class="empty-state-hint">${
        filterPersonId !== "all"
          ? "This person has no dated events. Add birth, death, or marriage dates."
          : "Add birth, death, or marriage dates to people and they'll appear on the timeline."
      }</p>
    </div>`;
    return;
  }

  if (mode === "branches") {
    renderBranchesGrid(container, entries);
  } else {
    renderStreamFeed(container, entries, filterPersonId === "all");
  }

  // Wire person-link clicks within timeline (shared by both modes)
  container.querySelectorAll(".person-link").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      showPersonPanel(a.dataset.personId);
    });
  });
}

// ── Full-width chronological stream (default mode) ──────────────
// Markup contract (W2/W4 build on this):
//   #timeline-entries.tstream.tstream-feed
//     .tstream-decade-nav            (right-edge minimap; one button per decade)
//     section.tstream-decade-group#tl-decade-{D}[data-decade="{D}"]
//       .tstream-decade              (sticky pill, "{D}s")
//       <buildStreamCellHtml(...)>   (one .tstream-entry per event, UNCHANGED)
// Lane accent: each .tstream-entry carries data-lane="{laneId}" and renders a
// .tstream-lane-chip. Legend focus adds .lane-focused on .tstream-feed and
// .lane-match on the chosen branch's entries (non-matches dim via CSS).
// "Where they are now": a present-day capstone of living family members, so the
// feed ends on the living rather than trailing into archival notes. Living = no
// death date and a birth year within ~105 years of now.
function buildLivingNowHtml() {
  const CUR = new Date().getFullYear();
  const living = [];
  for (const p of S.DATA.people) {
    if (p.death_date || !p.birth_date) continue;
    const by = parseInt(p.birth_date.substring(0, 4));
    if (!by || by < CUR - 105) continue;
    living.push({ p, by });
  }
  if (living.length < 2) return "";
  const res = {};
  for (const e of (S.DATA.events || [])) {
    if (e.event_type !== "residence" || !e.place) continue;
    if (!res[e.person_id] || (e.date || "") > (res[e.person_id].date || "")) res[e.person_id] = e;
  }
  living.sort((a, b) => a.by - b.by); // eldest first
  const cards = living.map(({ p, by }) => {
    const loc = (res[p.id] && res[p.id].place) || p.birth_place || "";
    return `<div class="tnow-card">${personThumb(p.id, 46)}<div class="tnow-body">` +
      `<div class="tnow-name">${personLink(p.id)}</div>` +
      `<div class="tnow-meta">age ${CUR - by}${loc ? " · " + escapeHtml(loc) : ""}</div></div></div>`;
  }).join("");
  return `<section class="tstream-now-group" id="tl-now">` +
    `<div class="tstream-decade tstream-now-pill">Where they are now</div>` +
    `<div class="tnow-grid">${cards}</div></section>`;
}

function renderStreamFeed(container, entries, showNow) {
  if (_decadeObserver) { _decadeObserver.disconnect(); _decadeObserver = null; }

  const laneMeta = _buildLaneMeta();
  const nowHtml = showNow ? buildLivingNowHtml() : "";

  // For historical-context inserts: the family's year span + military events.
  const allYears = entries.map((e) => e.year).filter(Boolean);
  const minY = allYears.length ? Math.min(...allYears) : 0;
  const maxY = allYears.length ? Math.max(...allYears) : 0;
  const military = (S.DATA.events || [])
    .filter((e) => e.event_type === "military" && e.date)
    .map((e) => ({ pid: e.person_id, year: parseInt(e.date.substring(0, 4)) }));
  // All place strings across the family, for region-gating historical eras.
  const placesText = [
    ...S.DATA.people.flatMap((p) => [p.birth_place, p.death_place]),
    ...(S.DATA.events || []).map((e) => e.place),
    ...(S.DATA.unions || []).map((u) => u.union_place),
  ].filter(Boolean).join(" | ").toLowerCase();
  const backstories = computeBackstoryAnchors(entries, placesText);

  // Group by decade, OMIT empty decades (no continuous backfill here)
  const byDecade = {};
  for (const e of entries) {
    const decade = Math.floor(e.year / 10) * 10;
    if (!byDecade[decade]) byDecade[decade] = [];
    byDecade[decade].push(e);
  }
  const decades = Object.keys(byDecade).map(Number).sort((a, b) => a - b);

  // Right-edge decade minimap (condensed if many decades)
  const condensed = decades.length > 12;
  let nav = `<nav class="tstream-decade-nav${condensed ? " tstream-decade-nav-condensed" : ""}" aria-label="Jump to decade">`;
  for (const d of decades) {
    nav += `<button type="button" class="tstream-nav-btn" data-decade="${d}">${d}s</button>`;
  }
  if (nowHtml) nav += `<button type="button" class="tstream-nav-btn tstream-nav-now" data-decade="now">Now</button>`;
  nav += `</nav>`;

  let html = `<div class="tstream tstream-feed">${nav}`;
  for (const decade of decades) {
    html += `<section class="tstream-decade-group" id="tl-decade-${decade}" data-decade="${decade}">`;
    html += `<div class="tstream-decade">${decade}s</div>`;
    (backstories[decade] || []).forEach((b) => { html += buildBackstoryHtml(b); });
    html += buildEraInserts(decade, minY, maxY, military, placesText);
    html += buildStreamCellHtml(byDecade[decade], laneMeta);
    html += `</section>`;
  }
  html += nowHtml;
  html += `</div>`;
  container.innerHTML = html;

  // Progressive face-aware framing. Cards render correct (object-fit:contain
  // over a blurred fill) with no JS; here we measure each photo's runtime
  // aspect on load and opt into .is-cover (crop) with a face-centroid
  // object-position ONLY for portrait/group shots that have faces and whose
  // aspect is close enough to the 4:5 stage that a crop reads intentionally.
  _wirePhotoFraming(container);

  // Re-apply any active lane focus class
  _applyLaneFocusClass(container);

  // Wire minimap buttons → smooth scroll to the decade group
  container.querySelectorAll(".tstream-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.decade === "now" ? "tl-now" : `tl-decade-${btn.dataset.decade}`;
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // IntersectionObserver: highlight the active decade in the minimap as you scroll
  const scrollRoot = container.closest(".timeline-container") || null;
  _decadeObserver = new IntersectionObserver(
    (observed) => {
      for (const ent of observed) {
        if (ent.isIntersecting) {
          const d = ent.target.dataset.decade;
          container.querySelectorAll(".tstream-nav-btn").forEach((b) => {
            b.classList.toggle("active", b.dataset.decade === d);
          });
        }
      }
    },
    { root: scrollRoot, rootMargin: "0px 0px -75% 0px", threshold: 0 }
  );
  container.querySelectorAll(".tstream-decade-group").forEach((g) => _decadeObserver.observe(g));
}

// ── Swim-lane grid (opt-in "Branches" lens) ─────────────────────
// This is the ORIGINAL renderTimeline body, extracted verbatim minus the
// removed in-grid stream column. Heights stay aligned across lanes per decade.
function renderBranchesGrid(container, entries) {
  if (_decadeObserver) { _decadeObserver.disconnect(); _decadeObserver = null; }

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

  const colCount = activeLanes.length;
  let html = `<div class="timeline-grid" style="--lane-count:${colCount}">`;

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
  html += `</div>`;

  // One row per decade
  for (const decade of decades) {
    html += `<div class="timeline-row">`;
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
        html += `
          <div class="timeline-entry${isCross ? " timeline-cross-marriage" : ""}${e.type === "photo" ? " timeline-photo-entry" : ""}" data-type="${e.type}" data-year="${e.year}" data-person-id="${e.personId || ""}">
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
}

// Wire per-photo runtime framing. Default markup is contain-over-blur (never
// crops a face). After an img loads we measure naturalWidth/Height and, when
// the photo qualifies, switch to a face-aware cover crop. A self-removing error
// handler hides broken imgs so they don't leave a blank stage.
//
// The 4:5 stage target aspect is 0.8 (w/h). We allow cover only when the
// runtime aspect is within ~0.6×–1.6× of that (≈0.48–1.28) so we never crop a
// wildly different shape; everything else stays contained.
const _STAGE_ASPECT = 4 / 5; // 0.8
function _wirePhotoFraming(container) {
  const imgs = container.querySelectorAll(".tstream-photo-stage .tstream-photo-img");
  imgs.forEach((img) => {
    const apply = () => {
      // Fade-in flip (P2): mark loaded so the .js-fade opacity transition runs.
      img.classList.add("is-loaded");
      const nw = img.naturalWidth || 0;
      const nh = img.naturalHeight || 0;
      if (!nw || !nh) return;
      const aspect = nw / nh; // w/h

      // Resolve the photo's stored facts from its src path (no leading slash).
      const path = (img.getAttribute("src") || "").replace(/^\//, "");
      const photo = S.PHOTOS_MAP ? S.PHOTOS_MAP[path] : null;
      const regions = photo?.face_regions || [];
      const ptype = photo?.photo_type || "photo";

      const aspectOk = aspect >= _STAGE_ASPECT * 0.6 && aspect <= _STAGE_ASPECT * 1.6;
      const typeOk = ptype === "portrait" || ptype === "group";
      if (regions.length >= 1 && typeOk && aspectOk) {
        // Face centroid → object-position. x/y/w/h are normalized 0-1.
        let sx = 0, sy = 0;
        for (const r of regions) {
          sx += r.x + r.w / 2;
          sy += r.y + r.h / 2;
        }
        const cx = Math.min(1, Math.max(0, sx / regions.length));
        const cy = Math.min(1, Math.max(0, sy / regions.length));
        img.style.objectPosition = `${(cx * 100).toFixed(1)}% ${(cy * 100).toFixed(1)}%`;
        img.classList.add("is-cover");
      }
    };

    if (img.complete && img.naturalWidth) {
      apply();
    } else {
      img.addEventListener("load", apply, { once: true });
      img.addEventListener("error", () => { img.style.visibility = "hidden"; }, { once: true });
    }
  });
}

// Build a quick {laneId: {label, color}} lookup from S.LANES.
function _buildLaneMeta() {
  const meta = {};
  for (const lane of S.LANES) meta[lane.id] = { label: lane.label, color: lane.color };
  return meta;
}

export function toggleTimelineAlignment() {
  TIMELINE_ALIGNED = !TIMELINE_ALIGNED;
  localStorage.setItem("timelineAligned", TIMELINE_ALIGNED);
  const btn = document.getElementById("timeline-align-toggle");
  if (btn) btn.textContent = TIMELINE_ALIGNED ? "Compact" : "Aligned";
  renderTimeline(document.getElementById("timeline-filter")?.value || "all");
}

// Flip between the stream feed and the branches grid, persist, re-render.
// Mirrors toggleTimelineAlignment. Button label shows the OTHER mode (the
// destination of a click): "Branches" while in stream, "Stream" in branches.
export function toggleTimelineMode() {
  TIMELINE_MODE = TIMELINE_MODE === "stream" ? "branches" : "stream";
  localStorage.setItem("timelineMode", TIMELINE_MODE);
  renderTimeline(document.getElementById("timeline-filter")?.value || "all", TIMELINE_MODE);
}

// Keep header controls in sync with the active mode:
//  - mode toggle button label
//  - alignment toggle only relevant in branches mode (hidden in stream)
//  - lane legend only shown in stream mode
function _syncTimelineControls() {
  const modeBtn = document.getElementById("timeline-view-toggle");
  if (modeBtn) modeBtn.textContent = TIMELINE_MODE === "stream" ? "Branches" : "Stream";

  const alignBtn = document.getElementById("timeline-align-toggle");
  if (alignBtn) alignBtn.style.display = TIMELINE_MODE === "branches" ? "" : "none";

  renderTimelineLegend();
}

// ── Lane legend / filter bar (stream mode only) ─────────────────
// Rendered into #timeline-legend. Each chip highlights one branch and dims
// the rest in the feed; clicking the active chip clears the focus.
export function renderTimelineLegend() {
  const host = document.getElementById("timeline-legend");
  if (!host) return;
  if (TIMELINE_MODE !== "stream" || S.LANES.length === 0) {
    host.innerHTML = "";
    host.style.display = "none";
    return;
  }
  host.style.display = "";
  let html = "";
  for (const lane of S.LANES) {
    const active = LANE_FOCUS === lane.id;
    html += `<button type="button" class="tstream-legend-chip${active ? " active" : ""}" data-lane="${lane.id}">
      <span class="tstream-legend-dot" style="background:${lane.color}"></span>
      ${escapeHtml(lane.label)}
    </button>`;
  }
  host.innerHTML = html;
  host.querySelectorAll(".tstream-legend-chip").forEach((chip) => {
    chip.addEventListener("click", () => focusTimelineLane(chip.dataset.lane));
  });
}

// Highlight a branch (single-select). Re-clicking the active branch clears it.
export function focusTimelineLane(laneId) {
  LANE_FOCUS = LANE_FOCUS === laneId ? null : laneId;
  renderTimelineLegend();
  const container = document.getElementById("timeline-entries");
  if (container) _applyLaneFocusClass(container);
}

// Toggle the dim class on the feed and mark matching entries. We dim
// non-matching .tstream-entry rather than recolor — reuses the app's
// fog-of-war "fade what's not in focus" aesthetic.
function _applyLaneFocusClass(container) {
  const feed = container.querySelector(".tstream-feed");
  if (!feed) return;
  feed.classList.toggle("lane-focused", !!LANE_FOCUS);
  feed.querySelectorAll(".tstream-entry").forEach((el) => {
    const match = LANE_FOCUS && el.dataset.lane === LANE_FOCUS;
    el.classList.toggle("lane-match", !!match);
  });
}

// ── Photo-first card ────────────────────────────────────────────
// Returns the `.tstream-card.tstream-photo-card` markup for a photo entry —
// the photo IS the card (full-bleed) with a caption/meta overlay. Reusable by
// a future standalone photo view and by clustering.
//
// Contract:
//   buildPhotoCardHtml(entry, laneChipHtml = "")
//   entry: a photo entry from gatherTimelineEntries / clusterPhotoEntries
//     {photoPath, title, dateDisplay, year, personId, place,
//      cluster?, clusterRest?, clusterPaths?, photoType, faceRegions}
//   laneChipHtml: pre-rendered .tstream-lane-chip span (or "") to place in the
//     overlay meta row. Caller owns the .tstream-entry wrapper + rail.
//
// The img defaults to object-fit:contain over a blurred fill (never crops a
// face); renderStreamFeed opts an img into .is-cover with a face-aware
// object-position after measuring its runtime aspect on load.
export function buildPhotoCardHtml(entry, laneChipHtml = "") {
  const e = entry;
  const safeAlt = (e.title || "").replace(/'/g, "\\'");

  // Cluster cards open the whole set in the lightbox (photoList = all members);
  // single cards open just themselves.
  const listArg = e.cluster && e.clusterPaths && e.clusterPaths.length > 1
    ? `[${e.clusterPaths.map((p) => `'${p.replace(/'/g, "\\'")}'`).join(",")}]`
    : "null";
  const onClick = `openLightbox('/${e.photoPath}', '${safeAlt}', '${e.photoPath}', ${listArg})`;

  const overlay = `
    <div class="tstream-photo-scrim" aria-hidden="true"></div>
    <div class="tstream-photo-overlay">
      ${e.title ? `<div class="tstream-photo-caption">${e.title}</div>` : ""}
      <div class="tstream-photo-overlay-meta">
        ${e.personId ? personThumb(e.personId, 22) : ""}
        <span class="tstream-photo-date">${escapeHtml(e.dateDisplay || e.year)}</span>
        ${e.place ? `<span class="tstream-photo-place"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:3px"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>${escapeHtml(e.place)}</span>` : ""}
        ${laneChipHtml}
      </div>
    </div>`;

  // Cluster → hero + filmstrip (collage-safe: hero is always full size).
  if (e.cluster && Array.isArray(e.clusterRest) && e.clusterRest.length > 0) {
    const SHOWN = 2; // hero + up to 2 strip thumbs (cap visible tiles at 3)
    const stripMembers = e.clusterRest.slice(0, SHOWN);
    const overflow = e.members.length - 1 - stripMembers.length;
    let strip = `<div class="tstream-cluster-strip">`;
    for (const m of stripMembers) {
      strip += `<div class="tstream-cluster-thumb" style="background-image:url(/${m.photoPath})"></div>`;
    }
    if (overflow > 0) {
      strip += `<div class="tstream-cluster-more">+${overflow}</div>`;
    }
    strip += `</div>`;
    return `
      <div class="tstream-card tstream-photo-card tstream-photo-card--cluster">
        <div class="tstream-photo-stage" onclick="${onClick}">
          <div class="tstream-photo-blurfill" aria-hidden="true" style="background-image:url(/${e.photoPath})"></div>
          <img class="tstream-photo-img" src="/${e.photoPath}" alt="${escapeHtml(e.title || "")}" loading="lazy" />
          ${overlay}
        </div>
        ${strip}
      </div>`;
  }

  // Single hero card.
  return `
    <div class="tstream-card tstream-photo-card">
      <div class="tstream-photo-stage" onclick="${onClick}">
        <div class="tstream-photo-blurfill" aria-hidden="true" style="background-image:url(/${e.photoPath})"></div>
        <img class="tstream-photo-img" src="/${e.photoPath}" alt="${escapeHtml(e.title || "")}" loading="lazy" />
        ${overlay}
      </div>
    </div>`;
}

// `laneMeta` (optional) is the {laneId:{label,color}} map from _buildLaneMeta.
// When supplied (stream mode) each entry gets a data-lane attribute and a
// .tstream-lane-chip. Omitting it (the in-grid/branches reuse path, if any)
// keeps the original markup intact.
export function buildStreamCellHtml(entries, laneMeta = null) {
  let html = "";
  for (const e of entries) {
    const color = e.type === "photo"
      ? (EVENT_COLORS.photo || "#d4a843")
      : (EVENT_COLORS[e.type] || EVENT_COLORS.custom || "#b066e0");

    const lm = laneMeta && e.lane ? laneMeta[e.lane] : null;
    const laneAttr = laneMeta && e.lane ? ` data-lane="${e.lane}"` : "";
    const laneChip = lm
      ? `<span class="tstream-lane-chip"><span class="tstream-lane-chip-dot" style="background:${lm.color}"></span>${escapeHtml(lm.label)}</span>`
      : "";

    if (e.type === "photo" && e.photoPath) {
      html += `
        <div class="tstream-entry tstream-photo-entry"${laneAttr}>
          <div class="tstream-rail"><div class="tstream-dot" style="border-color:${color}"></div></div>
          ${buildPhotoCardHtml(e, laneChip)}
        </div>`;
    } else {
      const t = STREAM_TREATMENTS[e.type];
      if (t?.tier === "milestone") {
        // Richer milestone card (birth / death / marriage) — carries the same
        // data-lane + lane chip so legend focus keeps working.
        html += buildMilestoneCellHtml(e, t, color, laneAttr, laneChip);
      } else {
        // Routine life event — stays quiet/flat so milestones stand out.
        html += `
        <div class="tstream-entry tstream-event-flat"${laneAttr}>
          <div class="tstream-flat-dot" style="background:${color}"></div>
          <div class="tstream-flat-body">
            ${e.personId ? personThumb(e.personId, 20) : ""}
            <span class="tstream-flat-date">${escapeHtml(e.dateDisplay || e.year)}</span>
            <span class="tstream-flat-title">${e.title}</span>
            ${e.personId ? `<span class="tstream-flat-person">${personLink(e.personId)}</span>` : ""}
            ${laneChip}
          </div>
        </div>`;
      }
    }
  }
  return html;
}

// Shared place-row markup (pin SVG + escaped place), reused across milestone
// variants. Returns "" when there's no place.
function _placeRowHtml(place) {
  if (!place) return "";
  return `<div class="tstream-place-row"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:3px"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>${escapeHtml(place)}</div>`;
}

// ── Milestone card (birth / death / marriage) ───────────────────
// A richer .tstream-card variant that breaks the flat rhythm for life's anchor
// events. Returns a full .tstream-entry (rail + dot reused from the photo path)
// so it shares the lane-focus + person-click wiring. `e.title` is raw HTML
// (already contains personLink for one or both names) — never re-escape it.
function buildMilestoneCellHtml(e, treatment, color, laneAttr, laneChip) {
  const variant = treatment.variant;
  const dateText = escapeHtml(e.dateDisplay || e.year);
  const placeRow = _placeRowHtml(e.place);

  let body;
  if (variant === "marriage") {
    // Both partner thumbs flanking a union glyph; guard a missing partner2.
    const thumbs = e.partner2Id
      ? `${personThumb(e.personId, 34)}<span class="tstream-marriage-glyph" aria-hidden="true">&#9829;</span>${personThumb(e.partner2Id, 34)}`
      : personThumb(e.personId, 34);
    body = `
        <div class="tstream-marriage-thumbs">${thumbs}</div>
        <div class="tstream-milestone-text">
          <div class="tstream-milestone-meta"><span class="tstream-date">${dateText}</span>${laneChip}</div>
          <div class="tstream-title">${e.title}</div>
          ${placeRow}
        </div>`;
  } else {
    // birth / death share structure: thumb + eyebrow + date + title + place.
    const eyebrow = variant === "birth" ? "Born" : "Died";
    body = `
        ${e.personId ? `<div class="tstream-milestone-thumb">${personThumb(e.personId, 30)}</div>` : ""}
        <div class="tstream-milestone-text">
          <div class="tstream-milestone-eyebrow">${eyebrow}</div>
          <div class="tstream-milestone-meta"><span class="tstream-date">${dateText}</span>${laneChip}</div>
          <div class="tstream-title">${e.title}</div>
          ${placeRow}
        </div>`;
  }

  return `
        <div class="tstream-entry tstream-milestone tstream-milestone--${variant}"${laneAttr}>
          <div class="tstream-rail"><div class="tstream-dot" style="border-color:${color}"></div></div>
          <div class="tstream-card tstream-milestone-card">
            <div class="tstream-milestone-body">${body}</div>
          </div>
        </div>`;
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
// Handles both the branches grid (.timeline-entry, data-person-id) and the
// stream feed (.tstream-entry, whose person link/thumb expose data-person-id).
document.getElementById("timeline-entries")?.addEventListener("click", (e) => {
  if (e.target.closest("a, img, [onclick]")) return;
  const gridEntry = e.target.closest(".timeline-entry");
  if (gridEntry?.dataset.personId) {
    showPersonPanel(gridEntry.dataset.personId);
    return;
  }
  const streamEntry = e.target.closest(".tstream-entry");
  if (streamEntry) {
    const pid = streamEntry.querySelector("[data-person-id]")?.dataset.personId;
    if (pid) showPersonPanel(pid);
  }
});
