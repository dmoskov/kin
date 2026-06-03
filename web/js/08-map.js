// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

export const GEOCODE = {
  // ── Eastern Europe / Middle East ──
  "Odessa, Russia":                               [46.48, 30.73],
  "Kamunetz-Podolsk, Russia":                     [48.68, 26.58],
  "Kamenitz-Podolsk, Russia":                     [48.68, 26.58],
  "Kamenitz-Podolsk, Russia (near Polish border)":[48.68, 26.58],
  "Kamminetz-Poddsk, Russia":                     [48.68, 26.58],
  "Russia":                                       [55.75, 37.62],
  "Russia / Poland":                              [52.23, 21.01],
  "Poland / Russia":                              [52.23, 21.01],
  "Poland":                                       [52.23, 21.01],
  "Romania":                                      [44.43, 26.10],
  "Constanti, Romania":                           [44.17, 28.63],
  "Kostence (Constanța), Romania":                [44.17, 28.63],
  "Morocco":                                      [31.79, -7.09],
  "Istanbul, Turkey":                             [41.01, 28.98],
  "Turkey":                                       [39.29, 35.23],
  // ── Iceland ──
  "Iceland":                                      [64.96, -19.02],
  // ── England ──
  "Liverpool, Lancashire, England":               [53.41, -2.98],
  "Chester, England":                             [53.19, -2.89],
  "Harthill, Cheshire, England":                  [53.22, -2.82],
  // ── Canada ──
  "Toronto, Ontario":                             [43.70, -79.42],
  "Ontario":                                      [51.25, -85.32],
  "Canada":                                       [56.13, -106.35],
  "Quebec, Canada":                               [46.81, -71.21],
  // ── New England ──
  "Boston, MA":                                   [42.36, -71.06],
  "Boston, Massachusetts":                        [42.36, -71.06],
  "Boston Harbor Front, Boston, Massachusetts, USA": [42.36, -71.05],
  "Boston Harbor, Boston, Massachusetts, USA":    [42.36, -71.05],
  "North End, Boston, Massachusetts":             [42.365, -71.055],
  "West End, Boston, Massachusetts, USA":         [42.364, -71.064],
  "East Boston, Massachusetts, USA":              [42.375, -71.039],
  "132 Portland Street, Boston, MA":              [42.363, -71.062],
  "Salem Street, Boston, MA":                     [42.365, -71.056],
  "Roxbury, MA":                                  [42.33, -71.09],
  "Roxbury, Massachusetts":                       [42.33, -71.09],
  "Brookline, Massachusetts":                     [42.333, -71.119],
  "Cambridge, MA":                                [42.374, -71.11],
  "Cambridge, Massachusetts":                     [42.374, -71.11],
  "Harvard University":                           [42.374, -71.117],
  "Harvard University, Cambridge, MA":            [42.374, -71.117],
  "Boston Latin School, Boston, MA":              [42.34, -71.10],
  "Natick, MA":                                   [42.284, -71.347],
  "Pepperell, MA":                                [42.665, -71.579],
  "Pepperell, Massachusetts":                     [42.665, -71.579],
  "Pepperill, MA":                                [42.665, -71.579],
  "Holliston, Massachusetts":                     [42.200, -71.425],
  "Massachusetts":                                [42.38, -72.03],
  "Yale University":                              [41.31, -72.93],
  // ── New York ──
  "New York, NY":                                 [40.71, -74.01],
  "Ossining, NY":                                 [41.16, -73.86],
  "Ithaca, NY":                                   [42.44, -76.50],
  "Ellis Island, New York Harbor":                [40.70, -74.04],
  "Ellis Island, New York Harbor, USA":           [40.70, -74.04],
  "Niagara Falls, NY":                            [43.09, -79.06],
  // ── Minnesota ──
  "Minnesota":                                    [44.98, -93.27],
  "Minneapolis, MN":                              [44.98, -93.27],
  "Minneapolis, Hennepin County, Minnesota":      [44.98, -93.27],
  "Twin Cities, MN":                              [44.96, -93.20],
  "Hennepin County, MN":                          [44.97, -93.27],
  "Hennepin County, Minnesota":                   [44.97, -93.27],
  "Crystal, MN":                                  [45.03, -93.36],
  "Crystal, Hennepin County, MN":                 [45.03, -93.36],
  "Golden Valley, MN":                            [44.99, -93.38],
  "Edina, MN":                                    [44.89, -93.35],
  "Bloomington, MN":                              [44.84, -93.30],
  "Bloomington, Minnesota":                       [44.84, -93.30],
  "Bloomington, Hennepin County, Minnesota":      [44.84, -93.30],
  "Rochester, MN":                                [44.02, -92.46],
  "Minneota, MN":                                 [44.56, -95.99],
  "Breckenridge, MN":                             [46.27, -96.58],
  "Lincoln County, MN":                           [44.41, -96.27],
  "Anoka, Anoka County, Minnesota":               [45.20, -93.39],
  "Ramsey County, Minnesota":                     [44.95, -93.13],
  "Wright, Carlton County, Minnesota":            [46.66, -92.56],
  "Riverside, St. Louis County, Minnesota":       [47.53, -92.18],
  "University of Minnesota":                      [44.97, -93.23],
  // ── Other Midwest / South ──
  "Evansville, IN":                               [37.97, -87.56],
  "Signature School, Evansville, IN":             [37.97, -87.56],
  "Illinois":                                     [40.63, -89.40],
  "Truro, Franklin County, Ohio":                 [39.97, -83.03],
  "Lexington, KY":                                [38.05, -84.50],
  "Alabama":                                      [33.26, -86.83],
  // ── Florida ──
  "Gainesville, FL":                              [29.65, -82.32],
  "Vanguard High School, Gainesville, FL":        [29.65, -82.33],
  "Vanguard High School, Ocala, FL":              [29.19, -82.15],
  "Ocala, FL":                                    [29.19, -82.14],
  "Ocala, Florida":                               [29.19, -82.14],
  "Longboat Key, FL":                             [27.41, -82.66],
  // ── Other US ──
  "San Francisco, CA":                            [37.77, -122.42],
  "San Diego, San Diego County, California":      [32.72, -117.16],
  "Maine":                                        [45.71, -68.86],
  "Chapel Hill, NC":                              [35.91, -79.06],
  "Washington, DC":                                [38.91, -77.04],
  "USA":                                          [39.83, -98.58],
  "United States":                                [39.83, -98.58],
};

// Runtime geocode results fetched from the server (Nominatim + DB cache).
// Populated by prefetchGeocode() on page load; map rendering awaits this.
export const GEOCODE_RUNTIME = {};

// Polling interval for background geocode resolution (ms)
export const _GEOCODE_POLL_MS = 3000;
let _geocodePlacesArr = [];

export async function prefetchGeocode() {
  const places = new Set();
  for (const p of S.DATA.people) {
    if (p.birth_place) places.add(p.birth_place);
    if (p.death_place) places.add(p.death_place);
  }
  for (const e of S.DATA.events || []) {
    if (e.place) places.add(e.place);
  }
  for (const u of S.DATA.unions || []) {
    if (u.union_place) places.add(u.union_place);
  }
  if (places.size === 0) return;
  _geocodePlacesArr = [...places];
  await _fetchGeocodeAndPoll(_geocodePlacesArr);
}

export async function _fetchGeocodeAndPoll(places) {
  try {
    const resp = await fetch("/api/geocode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(places),
    });
    const data = await resp.json();

    // New response format: { coords: {...}, pending: N }
    const coords = data.coords || data;
    const pending = data.pending || 0;

    let newResults = false;
    for (const [place, latlng] of Object.entries(coords)) {
      if (!GEOCODE_RUNTIME[place]) {
        GEOCODE_RUNTIME[place] = latlng;
        newResults = true;
      }
    }

    // If the map is visible and we got new results, refresh markers
    if (newResults && S.MAP) {
      // Clear existing markers and arcs before re-plotting
      for (const m of MAP_MARKERS) m.marker.remove();
      for (const a of MAP_ARCS) { a.polyline.remove(); if (a.hitArea) a.hitArea.remove(); if (a.arrowHead) a.arrowHead.remove(); if (a.boat) a.boat.remove(); }
      for (const m of MAP_GATEWAY_MARKERS) m.remove();
      MAP_MARKERS = [];
      MAP_ARCS = [];
      MAP_GATEWAY_MARKERS = [];
      buildMapEvents();
      const refreshed = _filterEventsByDepth(MAP_ALL_EVENTS);
      plotMapMarkers(refreshed);
      plotMigrationArcs(refreshed);
      buildGateways();
      renderGateways();
      renderMapRollCall();
    }

    // Poll again if places are still being resolved in the background
    if (pending > 0) {
      console.log(`[Geocode] ${Object.keys(coords).length} cached, ${pending} resolving in background…`);
      setTimeout(() => _fetchGeocodeAndPoll(places), _GEOCODE_POLL_MS);
    } else {
      console.log(`[Geocode] All ${Object.keys(GEOCODE_RUNTIME).length} places resolved.`);
    }
  } catch (_) {
    // Non-fatal: map falls back to the hardcoded GEOCODE table
  }
}

export function geocode(place) {
  if (!place) return null;
  // Curated hardcoded table takes priority (hand-verified coordinates)
  if (GEOCODE[place]) return GEOCODE[place];
  // Then server-resolved (Nominatim) coordinates
  if (GEOCODE_RUNTIME[place]) return GEOCODE_RUNTIME[place];
  // Fuzzy match against hardcoded table
  for (const [key, coords] of Object.entries(GEOCODE)) {
    if (place.includes(key) || key.includes(place)) return coords;
  }
  // Fuzzy match against runtime results
  for (const [key, coords] of Object.entries(GEOCODE_RUNTIME)) {
    if (place.includes(key) || key.includes(place)) return coords;
  }
  return null;
}

export const EVENT_COLORS = {
  birth:          "#4cd964",
  death:          "#888",
  immigration:    "#e74c3c",
  emigration:     "#e74c3c",
  education:      "#f5a623",
  career:         "#6c7cff",
  marriage:       "#ff6b8a",
  residence:      "#888",
  custom:         "#b066e0",
  naturalization: "#e74c3c",
  military:       "#6c7cff",
  religion:       "#b066e0",
  medical:        "#b066e0",
  photo:          "#d4a843",
};

let MAP_MARKERS = [];      // { marker, latlng, events: [{date, year, type, personId, desc, place}] }
let MAP_ARCS = [];         // { polyline, arrowHead, boat, boatBase, latlngs, personId, fromYear, toYear }
let MAP_ALL_EVENTS = [];   // flat list of {date, year, type, personId, place, desc, latlng}
let MAP_GATEWAY_MARKERS = []; // anchor markers at seaports (Ports of Entry)
let MAP_GATEWAYS = [];     // [{ name, latlng, arrivals: [{personId, year}] }] across the family
let mapAnimTimer = null;
let MAP_ANIMATING = false; // true while the time-lapse is playing (drives boat glide)

// Point at fraction t (0..1) along a polyline's vertex list.
function pointAlong(latlngs, t) {
  if (!latlngs || !latlngs.length) return null;
  const i = Math.max(0, Math.min(latlngs.length - 1, Math.round(t * (latlngs.length - 1))));
  return latlngs[i];
}
// The slider/filter/play controls are static DOM elements; their listeners are
// wired once (renderMap can run repeatedly via refreshAllViews).
let _mapListenersWired = false;

// Temporal brightness constants (MIN_YEAR computed dynamically from data)
let MIN_YEAR = 1650;    // will be recalculated from actual data
let MAX_YEAR = 2026;    // will be recalculated from actual data
export const BRIGHTNESS_FLOOR = 0.12;   // opacity for oldest events
export const BRIGHTNESS_CEIL  = 1.0;    // opacity for newest events
export const RADIUS_FLOOR     = 4;      // marker radius for oldest
export const RADIUS_CEIL      = 13;     // marker radius for newest
export const WEIGHT_FLOOR     = 1;      // arc thickness for oldest
export const WEIGHT_CEIL      = 3.5;    // arc thickness for newest

/**
 * Era definitions — each event gets an era tint based on its year.
 * Used to color-code the time period on the map.
 */
export const ERAS = [
  { label: "Colonial",      start: 0,    end: 1800, color: "#c9a84c" },
  { label: "Antebellum",    start: 1800, end: 1870, color: "#6a8fb5" },
  { label: "Immigration",   start: 1870, end: 1920, color: "#c05040" },
  { label: "Mid-Century",   start: 1920, end: 1970, color: "#3ea58e" },
  { label: "Modern",        start: 1970, end: 9999, color: "#8b7cff" },
];

export function getEra(year) {
  if (!year) return ERAS[ERAS.length - 1];
  for (const era of ERAS) {
    if (year >= era.start && year < era.end) return era;
  }
  return ERAS[ERAS.length - 1];
}

/**
 * Compute a 0-1 "recency" ratio for a given year relative to the visible range.
 * Older events → 0, events at maxYear → 1.
 */
export function recencyRatio(year, maxYear) {
  if (!year || !maxYear || maxYear <= MIN_YEAR) return 0.5;
  return Math.max(0, Math.min(1, (year - MIN_YEAR) / (maxYear - MIN_YEAR)));
}

/** Linearly interpolate between a and b by t ∈ [0,1] */
export function lerp(a, b, t) { return a + (b - a) * t; }

/**
 * Brighten / saturate a hex color toward white based on ratio (0=dim, 1=full).
 * At ratio=0 we darken to ~35% brightness; at ratio=1 we return the original.
 */
export function brightenColor(hex, ratio) {
  // Parse hex
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  // At low ratio, blend toward a dim grey
  const dimR = 40, dimG = 40, dimB = 50;
  const t = Math.max(0, Math.min(1, ratio));
  const outR = Math.round(lerp(dimR, r, t));
  const outG = Math.round(lerp(dimG, g, t));
  const outB = Math.round(lerp(dimB, b, t));
  return `rgb(${outR},${outG},${outB})`;
}

export function _computeMapFog() {
  // Compute fog distance from S.ORIGINAL_DATA so focus-mode filtering doesn't
  // cause ancestors/relatives to disappear from the map. Shared algorithm with
  // the tree layout via computeFogDistance (defined in 04-tree.js).
  return computeFogDistance(S.ORIGINAL_DATA || S.DATA);
}

function _filterEventsByDepth(events) {
  const maxFog = S.MAP_DEPTH >= 4 ? Infinity : S.MAP_DEPTH;
  return events.filter(e => (e.fogLevel || 0) <= maxFog);
}

export function buildMapEvents() {
  MAP_ALL_EVENTS = [];

  // The map shows ALL geo data in the database. Fog level is stored on each
  // event for styling (opacity/size) but is NOT used to exclude events — the
  // map is a geographic overview across the entire dataset. Viewer-based
  // filtering (fog-of-war) is a tree-view concern only.
  const fog = _computeMapFog();

  function personFog(pid) {
    return fog[pid] !== undefined ? Math.min(fog[pid], 4) : 4;
  }

  // Use S.ORIGINAL_DATA so focus-mode filtering doesn't hide map locations
  const src = S.ORIGINAL_DATA || S.DATA;
  // Births
  for (const p of src.people) {
    if (p.birth_place) {
      const ll = geocode(p.birth_place);
      if (ll) {
        MAP_ALL_EVENTS.push({
          date: p.birth_date || "",
          year: p.birth_date ? parseInt(p.birth_date.substring(0, 4)) : null,
          type: "birth",
          personId: p.id,
          fogLevel: personFog(p.id),
          place: p.birth_place,
          desc: `${personName(p.id)} born`,
          latlng: ll,
        });
      }
    }
    // Deaths
    if (p.death_place) {
      const ll = geocode(p.death_place);
      if (ll) {
        MAP_ALL_EVENTS.push({
          date: p.death_date || "",
          year: p.death_date ? parseInt(p.death_date.substring(0, 4)) : null,
          type: "death",
          personId: p.id,
          fogLevel: personFog(p.id),
          place: p.death_place,
          desc: `${personName(p.id)} died`,
          latlng: ll,
        });
      }
    }
  }
  // Life events
  for (const e of (src.events || [])) {
    if (!e.place) continue;
    const ll = geocode(e.place);
    if (!ll) continue;
    MAP_ALL_EVENTS.push({
      date: e.date || "",
      year: e.date ? parseInt(e.date.substring(0, 4)) : null,
      type: e.event_type,
      personId: e.person_id,
      fogLevel: personFog(e.person_id),
      place: e.place,
      desc: `${personName(e.person_id)} — ${escapeHtml(e.description || e.event_type)}`,
      latlng: ll,
    });
  }

  // Marriages
  for (const u of (src.unions || [])) {
    if (!u.union_place) continue;
    const minFog = Math.min(personFog(u.partner1_id), personFog(u.partner2_id));
    const ll = geocode(u.union_place);
    if (!ll) continue;
    MAP_ALL_EVENTS.push({
      date: u.union_date || "",
      year: u.union_date ? parseInt(u.union_date.substring(0, 4)) : null,
      type: "marriage",
      personId: u.partner1_id,
      partner2Id: u.partner2_id,
      fogLevel: minFog,
      place: u.union_place,
      desc: `${personName(u.partner1_id)} & ${personName(u.partner2_id)} married`,
      latlng: ll,
    });
  }

  // Photos with place or GPS coordinates
  if (src.photos) {
    for (const photo of src.photos) {
      // Prefer EXIF GPS coordinates; fall back to geocoding place name
      let ll = null;
      if (photo.lat != null && photo.lng != null) {
        ll = [photo.lat, photo.lng];
      } else if (photo.place) {
        ll = geocode(photo.place);
      }
      if (!ll) continue;
      const primaryPerson = (photo.tagged_people || [])[0];
      const pid = primaryPerson?.person_id;
      MAP_ALL_EVENTS.push({
        date: photo.date || "",
        year: photo.date ? parseInt(photo.date.substring(0, 4)) : null,
        type: "photo",
        personId: pid || "",
        fogLevel: pid ? personFog(pid) : 0,
        place: photo.place || "GPS location",
        desc: primaryPerson?.caption || "Photo",
        latlng: ll,
        photoPath: photo.file_path,
      });
    }
  }

  MAP_ALL_EVENTS.sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  // Compute dynamic year range from actual data
  const years = MAP_ALL_EVENTS.map((e) => e.year).filter(Boolean);
  if (years.length > 0) {
    MIN_YEAR = Math.min(...years);
    MAX_YEAR = Math.max(...years, new Date().getFullYear());
  }
}

export async function renderMap() {
  await S._geocodeReady;
  // Stop any in-flight time-lapse animation before tearing down the map, so the
  // old interval doesn't keep firing against the rebuilt map / stuck play button.
  if (mapAnimTimer) {
    clearInterval(mapAnimTimer);
    mapAnimTimer = null;
    const oldPlay = document.getElementById("map-play");
    if (oldPlay) {
      oldPlay.classList.remove("playing");
      oldPlay.innerHTML = "&#9654;";
    }
  }
  if (S.MAP) { S.MAP.remove(); S.MAP = null; }
  MAP_MARKERS = [];
  MAP_ARCS = [];
  MAP_GATEWAY_MARKERS = [];

  S.MAP = L.map("map", {
    center: [40, -40],
    zoom: 3,
    zoomControl: true,
    attributionControl: false,
  });

  // Map tiles — use appropriate style for current theme
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  const tileUrl = isLight
    ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  L.tileLayer(tileUrl, {
    maxZoom: 19,
    subdomains: "abcd",
  }).addTo(S.MAP);

  // Attribution (subtle)
  L.control.attribution({ prefix: false, position: "bottomright" })
    .addAttribution('&copy; <a href="https://carto.com/">CARTO</a>')
    .addTo(S.MAP);

  S.MAP.on("zoomend", _updatePhotoZoomScale);
  _updatePhotoZoomScale();

  buildMapEvents();
  const mapDepthEvents = _filterEventsByDepth(MAP_ALL_EVENTS);
  plotMapMarkers(mapDepthEvents);
  plotPhotoMarkers(mapDepthEvents);
  plotMigrationArcs(mapDepthEvents);
  buildGateways();
  renderGateways();
  renderMapRollCall();
  populateMapFilter(mapDepthEvents);
  document.getElementById("map-empty")?.classList.toggle("hidden", mapDepthEvents.length > 0);

  // Fit bounds
  const allLatLngs = mapDepthEvents.map((e) => e.latlng);
  if (allLatLngs.length > 0) {
    S.MAP.fitBounds(allLatLngs, { padding: [50, 50], maxZoom: 6 });
  }

  // Wire up slider — dynamic range from data
  const slider = document.getElementById("map-time-slider");
  const yearStartLabel = document.getElementById("slider-year-start");
  const yearEndLabel = document.getElementById("slider-year-end");
  slider.min = MIN_YEAR;
  slider.max = MAX_YEAR;
  slider.value = MAX_YEAR;
  yearStartLabel.textContent = MIN_YEAR;
  yearEndLabel.textContent = MAX_YEAR;
  // Wire control listeners once — these elements persist across renderMap calls,
  // so re-binding every time would stack duplicate handlers.
  if (!_mapListenersWired) {
    slider.addEventListener("input", () => {
      const maxYear = parseInt(slider.value);
      yearEndLabel.textContent = maxYear;
      updateMapForYear(maxYear);
    });
    document.getElementById("map-person-filter").addEventListener("change", () => {
      const maxYear = parseInt(slider.value);
      updateMapForYear(maxYear);
    });
    document.getElementById("map-play").addEventListener("click", toggleMapAnimation);
    document.getElementById("map-depth-select")?.addEventListener("change", (e) => {
      S.MAP_DEPTH = parseInt(e.target.value, 10);
      localStorage.setItem("ft-map-depth", String(S.MAP_DEPTH));
      renderMap();
    });
    _mapListenersWired = true;
  }
  const mapDepthSelect = document.getElementById("map-depth-select");
  if (mapDepthSelect) mapDepthSelect.value = String(S.MAP_DEPTH);
}

export function plotMapMarkers(events) {
  // Group events by person + place so each person gets their own dot
  const byPersonPlace = {};
  for (const e of events) {
    const key = (e.personId || "") + "@" + e.latlng.join(",");
    if (!byPersonPlace[key]) byPersonPlace[key] = { latlng: e.latlng, place: e.place, personId: e.personId, events: [] };
    byPersonPlace[key].events.push(e);
  }

  // Detect overlapping groups (same latlng, different people) and offset them
  const byCoord = {};
  for (const group of Object.values(byPersonPlace)) {
    const ck = group.latlng.join(",");
    if (!byCoord[ck]) byCoord[ck] = [];
    byCoord[ck].push(group);
  }

  // Co-located people (e.g. everyone recorded simply as "Boston") share ONE
  // marker at the true coordinate rather than being fanned out into fake,
  // specific-looking nearby points. Size grows with how many people are there,
  // and a tooltip/popup spell out who — honest about the location's precision.
  for (const groups of Object.values(byCoord)) {
    const latlng = groups[0].latlng;
    const place = groups[0].place;
    const events = groups.flatMap((g) => g.events);
    const peopleCount = new Set(groups.map((g) => g.personId).filter(Boolean)).size;
    const isCluster = peopleCount > 1;

    const newestYear = Math.max(...events.map((e) => e.year || MIN_YEAR));
    const ratio = recencyRatio(newestYear, MAX_YEAR);
    const primaryType = events[0].type;
    const baseColor = EVENT_COLORS[primaryType] || "#6c7cff";
    const fillColor = brightenColor(baseColor, ratio);
    const fillOpacity = lerp(BRIGHTNESS_FLOOR, BRIGHTNESS_CEIL, ratio);
    const baseRadius = lerp(RADIUS_FLOOR, RADIUS_CEIL, ratio);
    // Bigger blob = more people at this exact spot.
    const radius = Math.min(baseRadius + (peopleCount - 1) * 1.6, RADIUS_CEIL + 9);
    const era = getEra(newestYear);

    const marker = L.circleMarker(latlng, {
      radius,
      fillColor,
      fillOpacity,
      color: era.color,
      weight: 2,
    }).addTo(S.MAP);

    if (isCluster) {
      marker.bindTooltip(`${peopleCount} people · ${escapeHtml(place)}`, { direction: "top" });
    } else {
      marker.on("mouseover", (e) => {
        const primaryEvent = events[0];
        if (primaryEvent) {
          const containerPt = S.MAP.latLngToContainerPoint(e.latlng);
          const mapEl = document.getElementById("map");
          const mapRect = mapEl.getBoundingClientRect();
          showHovercardAt(primaryEvent.personId, mapRect.left + containerPt.x, mapRect.top + containerPt.y);
        }
      });
      marker.on("mouseout", () => { hideHovercard(); });
    }

    marker.on("click", () => {
      if (isCluster) {
        marker.openPopup();
      } else {
        const primaryEvent = events[0];
        if (primaryEvent) {
          showPersonPanel(primaryEvent.personId);
          router.navigate(`/map/person/${primaryEvent.personId}`);
        }
      }
    });

    const popupHtml = buildPlacePopup(place, events);
    marker.bindPopup(popupHtml, { maxWidth: 300, maxHeight: 320 });

    MAP_MARKERS.push({
      marker,
      latlng,
      origLatlng: latlng,
      events,
      placeKey: latlng.join(","),
    });
  }
}

export function buildPlacePopup(place, events) {
  let html = `<h4>${escapeHtml(place)}</h4>`;
  for (const e of events) {
    const year = e.year || "?";
    const dotColor = EVENT_COLORS[e.type] || "#6c7cff";
    const person = S.PEOPLE_MAP[e.personId];
    const profileSrc = person?._profilePhotoPath;
    let thumbHtml = "";
    if (profileSrc) {
      thumbHtml = croppedImg(profileSrc, person?.fullName || "", 20, person?._profileCrop, "map-popup-thumb");
    } else if (person) {
      const initial = (person.given_name || "?")[0];
      thumbHtml = `<span style="display:inline-flex;width:20px;height:20px;border-radius:50%;background:${person.gender === "female" ? "var(--node-female-bg)" : "var(--node-male-bg)"};border:1px solid ${person.gender === "female" ? "var(--female)" : "var(--male)"};align-items:center;justify-content:center;font-size:10px;font-weight:700;color:var(--text);vertical-align:middle;margin-right:4px">${initial}</span>`;
    }
    let descHtml = e.desc;
    if (person) descHtml = descHtml.replace(person.fullName, personLink(e.personId));
    if (e.partner2Id) {
      const p2 = S.PEOPLE_MAP[e.partner2Id];
      if (p2) descHtml = descHtml.replace(p2.fullName, personLink(e.partner2Id));
    }
    html += `<div class="popup-event">
      <span class="popup-year">${year}</span>
      <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${dotColor};margin:0 6px;vertical-align:middle"></span>
      ${thumbHtml}
      <span class="popup-person">${descHtml}</span>
      ${e.type === "photo" && e.photoPath ? `<img class="map-photo-popup-thumb" src="/${e.photoPath}" alt="" style="width:60px;height:40px;object-fit:cover;border-radius:4px;margin-top:4px;display:block" />` : ""}
    </div>`;
  }
  return html;
}

function _updatePhotoZoomScale() {
  const zoom = S.MAP.getZoom();
  const scale = Math.max(1, Math.min(2.5, 1 + (zoom - 5) * 0.15));
  document.getElementById("map")?.style.setProperty("--photo-zoom-scale", scale);
}

// Photo thumbnail markers on map
let MAP_PHOTO_MARKERS = [];

export function plotPhotoMarkers(events) {
  // Remove old photo markers
  for (const m of MAP_PHOTO_MARKERS) m.remove();
  MAP_PHOTO_MARKERS = [];

  // Filter to photo events with a photoPath
  const photoEvents = events.filter(e => e.type === "photo" && e.photoPath);
  if (!photoEvents.length) return;

  // Simple clustering: group by rounded lat/lng (3 decimal places ~ 100m)
  const clusters = {};
  for (const e of photoEvents) {
    const key = `${e.latlng[0].toFixed(3)},${e.latlng[1].toFixed(3)}`;
    if (!clusters[key]) clusters[key] = { latlng: e.latlng, events: [] };
    clusters[key].events.push(e);
  }

  for (const cluster of Object.values(clusters)) {
    const count = cluster.events.length;
    const firstPhoto = cluster.events[0];

    if (count === 1) {
      // Single photo: circular thumbnail marker
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-photo-marker"><img src="/${firstPhoto.photoPath}" alt="" /></div>`,
        iconSize: [48, 48],
        iconAnchor: [24, 24],
      });
      const marker = L.marker(cluster.latlng, { icon }).addTo(S.MAP);
      marker.on("click", () => {
        openLightbox("/" + firstPhoto.photoPath, "", firstPhoto.photoPath);
      });
      MAP_PHOTO_MARKERS.push(marker);
    } else {
      // Cluster: show first photo with count badge
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-photo-marker" style="position:relative"><img src="/${firstPhoto.photoPath}" alt="" /><span class="map-photo-count">${count}</span></div>`,
        iconSize: [48, 48],
        iconAnchor: [24, 24],
      });
      const marker = L.marker(cluster.latlng, { icon }).addTo(S.MAP);

      // Popup with thumbnail grid
      const thumbsHtml = cluster.events.map(e =>
        `<img src="/${e.photoPath}" alt="" onclick="openLightbox('/${e.photoPath}', '', '${e.photoPath}')" />`
      ).join("");
      marker.bindPopup(`<div class="map-cluster-grid">${thumbsHtml}</div>`, { maxWidth: 280 });
      MAP_PHOTO_MARKERS.push(marker);
    }
  }
}

// Assign consistent colors to people for arcs
export const PERSON_COLORS = {};
export const ARC_PALETTE = [
  "#6c7cff", "#ff6b8a", "#f5a623", "#4cd964", "#b066e0",
  "#e74c3c", "#4a90d9", "#d94a8c", "#50e3c2", "#f8e71c",
];
let arcColorIdx = 0;

export function getPersonColor(personId) {
  if (!PERSON_COLORS[personId]) {
    PERSON_COLORS[personId] = ARC_PALETTE[arcColorIdx % ARC_PALETTE.length];
    arcColorIdx++;
  }
  return PERSON_COLORS[personId];
}

// Known immigrant seaports / arrival stations, with hardcoded coordinates so
// detection never depends on the (flaky) geocoder. Each `match` substring is
// tested against an event's place, description, and notes — so a port named
// only in free text still counts. First match wins.
const SEAPORTS = [
  { match: "ellis island",         name: "Ellis Island",         latlng: [40.6995, -74.0397] },
  { match: "castle garden",        name: "Castle Garden",        latlng: [40.7036, -74.0170] },
  { match: "castle clinton",       name: "Castle Garden",        latlng: [40.7036, -74.0170] },
  { match: "angel island",         name: "Angel Island",         latlng: [37.8607, -122.4326] },
  { match: "galveston",            name: "Galveston",            latlng: [29.3013, -94.7977] },
  { match: "port of new york",     name: "Port of New York",     latlng: [40.6995, -74.0397] },
  { match: "port of boston",       name: "Port of Boston",       latlng: [42.3601, -71.0489] },
  { match: "port of philadelphia", name: "Port of Philadelphia", latlng: [39.9434, -75.1435] },
  { match: "port of baltimore",    name: "Port of Baltimore",    latlng: [39.2660, -76.5790] },
  { match: "port of new orleans",  name: "Port of New Orleans",  latlng: [29.9450, -90.0660] },
];

// Scan one or more free-text fields for any known seaport; return the matched
// SEAPORTS entry, or null. Used by arcs (boat), gateways, and the roll-call.
export function detectSeaport(...texts) {
  const hay = texts.filter(Boolean).join(" · ").toLowerCase();
  if (!hay) return null;
  return SEAPORTS.find((s) => hay.includes(s.match)) || null;
}

export function isSeaportPlace(place) {
  return !!detectSeaport(place);
}

export function plotMigrationArcs(events) {
  // Group events by person, sorted chronologically
  const byPerson = {};
  for (const e of events) {
    if (!byPerson[e.personId]) byPerson[e.personId] = [];
    byPerson[e.personId].push(e);
  }

  for (const [personId, personEvents] of Object.entries(byPerson)) {
    // Deduplicate consecutive same-location
    const waypoints = [];
    for (const e of personEvents) {
      const key = e.latlng.join(",");
      if (waypoints.length === 0 || waypoints[waypoints.length - 1].key !== key) {
        waypoints.push({ latlng: e.latlng, key, year: e.year, date: e.date, place: e.place });
      }
    }

    if (waypoints.length < 2) continue;

    const baseColor = getPersonColor(personId);
    for (let i = 0; i < waypoints.length - 1; i++) {
      const from = waypoints[i];
      const to = waypoints[i + 1];
      const ratio = recencyRatio(to.year, MAX_YEAR);
      const arcColor = brightenColor(baseColor, ratio);
      const arcOpacity = lerp(BRIGHTNESS_FLOOR, 0.8, ratio);
      const arcWeight = lerp(WEIGHT_FLOOR, WEIGHT_CEIL, ratio);

      // Draw a curved line with an arrowhead
      const latlngs = curvedPath(from.latlng, to.latlng);

      // Invisible wider hit-area polyline for easier mouse interaction
      const hitArea = L.polyline(latlngs, {
        color: arcColor,
        weight: Math.max(arcWeight * 4, 16),
        opacity: 0,
        interactive: true,
        className: "arc-hit-area",
      }).addTo(S.MAP);

      const polyline = L.polyline(latlngs, {
        color: arcColor,
        weight: arcWeight,
        opacity: arcOpacity,
        dashArray: "6,4",
        interactive: false,
      }).addTo(S.MAP);

      // Arrow decorator at the end
      const arrowHead = L.circleMarker(to.latlng, {
        radius: lerp(2, 4, ratio),
        fillColor: arcColor,
        fillOpacity: lerp(BRIGHTNESS_FLOOR, 0.9, ratio),
        color: arcColor,
        weight: 1,
      }).addTo(S.MAP);

      // Tooltip on hover — bound to hit area for easier triggering
      hitArea.bindTooltip(
        `${personName(personId)}: ${escapeHtml(from.place || "?")} → ${escapeHtml(to.place || "?")} (${from.year || "?"} – ${to.year || "?"})`,
        { sticky: true, className: "arc-tooltip" }
      );

      // Hover highlight: thicken and brighten the visible arc
      hitArea.on("mouseover", () => {
        polyline.setStyle({
          weight: arcWeight + 3,
          opacity: Math.min(arcOpacity + 0.3, 1),
        });
        arrowHead.setStyle({ radius: lerp(2, 4, ratio) + 2 });
      });
      hitArea.on("mouseout", () => {
        polyline.setStyle({ weight: arcWeight, opacity: arcOpacity });
        arrowHead.setStyle({ radius: lerp(2, 4, ratio) });
      });

      // Click: open popup with migration details for the person
      const popupContent = buildArcPopup(personId, from, to);
      hitArea.bindPopup(popupContent, { maxWidth: 280, className: "arc-popup" });

      // Boat on sea crossings ending at a known immigrant seaport. At rest it
      // sits ~70% along the curve (approaching port); during playback it glides
      // from origin to port (see updateMapForYear).
      let boat = null;
      const boatBase = latlngs[Math.floor(latlngs.length * 0.7)] || to.latlng;
      if (isSeaportPlace(to.place)) {
        boat = L.marker(boatBase, {
          icon: L.divIcon({
            className: "",
            html: `<div class="map-boat-marker" title="Sea passage to ${escapeHtml(to.place || "port")}">&#128674;</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          }),
          interactive: false,
          keyboard: false,
        }).addTo(S.MAP);
        boat.setOpacity(lerp(0.4, 1, ratio));
      }

      MAP_ARCS.push({
        polyline,
        hitArea,
        arrowHead,
        boat,
        boatBase,
        latlngs,
        personId,
        fromYear: from.year,
        toYear: to.year,
        _arcWeight: arcWeight,
        _arcOpacity: arcOpacity,
      });
    }
  }
}

// ── Ports of Entry: seaport gateways + the family roll-call ──────────

// Index every event whose place/description/notes names a known seaport into
// per-port arrival lists (one arrival per person per port, earliest year).
export function buildGateways() {
  const src = S.ORIGINAL_DATA || S.DATA;
  const byPort = {};
  for (const e of (src.events || [])) {
    const port = detectSeaport(e.place, e.description, e.notes);
    if (!port) continue;
    const g = byPort[port.name] || (byPort[port.name] = { name: port.name, latlng: port.latlng, arrivals: new Map() });
    const year = e.date ? parseInt(e.date.substring(0, 4)) : null;
    const prev = g.arrivals.get(e.person_id);
    if (prev === undefined || (year && (prev == null || year < prev))) g.arrivals.set(e.person_id, year ?? prev ?? null);
  }
  MAP_GATEWAYS = Object.values(byPort)
    .map((g) => ({
      name: g.name,
      latlng: g.latlng,
      arrivals: [...g.arrivals.entries()]
        .map(([personId, year]) => ({ personId, year }))
        .filter((a) => S.PEOPLE_MAP[a.personId])
        .sort((a, b) => (a.year || 9999) - (b.year || 9999)),
    }))
    .filter((g) => g.arrivals.length > 0)
    .sort((a, b) => b.arrivals.length - a.arrivals.length);
  return MAP_GATEWAYS;
}

function arrivalRowsHtml(entries) {
  return entries
    .filter(([pid]) => S.PEOPLE_MAP[pid])
    .sort((a, b) => (a[1] || 9999) - (b[1] || 9999))
    .map(([pid, year]) => `<div class="gateway-arrival">${personLink(pid)}<span class="gateway-arrival-year">${year || "?"}</span></div>`)
    .join("");
}

function renderGateways() {
  for (const m of MAP_GATEWAY_MARKERS) m.remove();
  MAP_GATEWAY_MARKERS = [];
  for (const g of MAP_GATEWAYS) {
    const count = g.arrivals.length;
    const size = Math.round(20 + Math.min(count, 12) * 1.8);
    const box = size + 18;
    const icon = L.divIcon({
      className: "",
      html: `<div class="map-gateway-marker" title="${escapeHtml(g.name)} — ${count} ${count === 1 ? "arrival" : "arrivals"}"><span class="map-gateway-anchor" style="font-size:${size}px">&#9875;</span><span class="map-gateway-count">${count}</span></div>`,
      iconSize: [box, box],
      iconAnchor: [box / 2, box / 2],
    });
    const marker = L.marker(g.latlng, { icon, zIndexOffset: 600 }).addTo(S.MAP);
    marker.bindPopup(
      `<div class="arc-popup-content"><div class="gateway-popup-header">&#9875; ${escapeHtml(g.name)}</div><div class="gateway-popup-sub">${count} ${count === 1 ? "arrival" : "arrivals"}</div>${arrivalRowsHtml(g.arrivals.map((a) => [a.personId, a.year]))}</div>`,
      { maxWidth: 260, className: "arc-popup" }
    );
    MAP_GATEWAY_MARKERS.push(marker);
  }
}

function rollCallGroup(name, latlng, entries, isPort) {
  const rows = arrivalRowsHtml(entries);
  const n = entries.filter(([pid]) => S.PEOPLE_MAP[pid]).length;
  const locate = latlng ? `<button type="button" class="roll-call-locate" data-lat="${latlng[0]}" data-lng="${latlng[1]}" title="Show on map">&#9678;</button>` : "";
  return `<details class="roll-call-group">
    <summary><span class="roll-call-name">${isPort ? "&#9875; " : ""}${escapeHtml(name)}</span><span class="roll-call-count">${n}</span>${locate}</summary>
    <div class="roll-call-people">${rows}</div>
  </details>`;
}

let _rollCallWired = false;
// The roll-call panel: ports of entry + other gathering places (a place where
// 4+ family members share events), each expandable to the people tied to it.
export function renderMapRollCall() {
  const panel = document.getElementById("map-roll-call");
  if (!panel) return;
  const body = panel.querySelector(".map-roll-call-body");
  if (!body) return;

  const byPlace = {};
  for (const e of MAP_ALL_EVENTS) {
    if (!e.place || !e.personId) continue;
    const g = byPlace[e.place] || (byPlace[e.place] = { place: e.place, latlng: e.latlng, people: new Map() });
    const cur = g.people.get(e.personId);
    if (cur === undefined || (e.year && (cur == null || e.year < cur))) g.people.set(e.personId, e.year ?? cur ?? null);
  }
  const GATHER_MIN = 4;
  const portNames = new Set(MAP_GATEWAYS.map((g) => g.name));
  const gathering = Object.values(byPlace)
    .map((g) => ({ place: g.place, latlng: g.latlng, count: g.people.size, people: [...g.people.entries()] }))
    .filter((g) => g.count >= GATHER_MIN && !portNames.has(g.place))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);

  let html = "";
  if (MAP_GATEWAYS.length) {
    html += `<div class="roll-call-section-title">&#9875; Ports of entry</div>`;
    for (const g of MAP_GATEWAYS) html += rollCallGroup(g.name, g.latlng, g.arrivals.map((a) => [a.personId, a.year]), true);
  }
  if (gathering.length) {
    html += `<div class="roll-call-section-title">Gathering places</div>`;
    for (const g of gathering) html += rollCallGroup(g.place, g.latlng, g.people, false);
  }
  body.innerHTML = html || `<div class="roll-call-empty">No notable places yet.</div>`;
  panel.classList.toggle("hidden", !html);

  if (!_rollCallWired) {
    document.getElementById("map-roll-call-toggle")?.addEventListener("click", () => {
      panel.classList.toggle("collapsed");
    });
    body.addEventListener("click", (ev) => {
      const loc = ev.target.closest(".roll-call-locate");
      if (loc && S.MAP) {
        ev.preventDefault();
        S.MAP.flyTo([parseFloat(loc.dataset.lat), parseFloat(loc.dataset.lng)], 6, { duration: 0.8 });
      }
    });
    _rollCallWired = true;
  }
}

export function buildArcPopup(personId, from, to) {
  const person = S.PEOPLE_MAP[personId];
  const profileSrc = person?._profilePhotoPath;
  let thumbHtml = "";
  if (profileSrc) {
    thumbHtml = croppedImg(profileSrc, person?.fullName || "", 28, person?._profileCrop, "map-popup-thumb arc-popup-thumb");
  } else if (person) {
    const initial = (person.given_name || "?")[0];
    thumbHtml = `<span class="arc-popup-avatar" style="background:${person.gender === "female" ? "var(--node-female-bg)" : "var(--node-male-bg)"};border-color:${person.gender === "female" ? "var(--female)" : "var(--male)"}">${initial}</span>`;
  }
  const nameHtml = person ? personLink(personId) : escapeHtml(personId);
  return `<div class="arc-popup-content">
    <div class="arc-popup-header">${thumbHtml} <strong>${nameHtml}</strong></div>
    <div class="arc-popup-route">
      <span class="arc-popup-place">${escapeHtml(from.place || "Unknown")}</span>
      <span class="arc-popup-year">${from.year || "?"}</span>
    </div>
    <div class="arc-popup-arrow">&#8595;</div>
    <div class="arc-popup-route">
      <span class="arc-popup-place">${escapeHtml(to.place || "Unknown")}</span>
      <span class="arc-popup-year">${to.year || "?"}</span>
    </div>
  </div>`;
}

export function curvedPath(from, to) {
  // Create a quadratic bezier curve between two lat/lng points
  const midLat = (from[0] + to[0]) / 2;
  const midLng = (from[1] + to[1]) / 2;
  // Offset perpendicular to the line for curvature
  const dLat = to[0] - from[0];
  const dLng = to[1] - from[1];
  const dist = Math.sqrt(dLat * dLat + dLng * dLng);
  const offset = dist * 0.15;
  const controlLat = midLat + (-dLng / dist) * offset;
  const controlLng = midLng + (dLat / dist) * offset;

  const points = [];
  const steps = 20;
  for (let t = 0; t <= 1; t += 1 / steps) {
    const lat = (1 - t) * (1 - t) * from[0] + 2 * (1 - t) * t * controlLat + t * t * to[0];
    const lng = (1 - t) * (1 - t) * from[1] + 2 * (1 - t) * t * controlLng + t * t * to[1];
    points.push([lat, lng]);
  }
  return points;
}

export function updateMapForYear(maxYear) {
  const badge = document.getElementById("map-year-badge");
  if (badge) badge.textContent = maxYear;
  const filterPersonId = document.getElementById("map-person-filter").value;

  // ── Markers: temporal brightness ──
  for (const m of MAP_MARKERS) {
    const visibleEvents = m.events.filter((e) => {
      const yearOk = !e.year || e.year <= maxYear;
      const personOk = filterPersonId === "all" || e.personId === filterPersonId;
      return yearOk && personOk;
    });

    if (visibleEvents.length > 0) {
      // Use the most recent visible event's year for brightness
      const newestYear = Math.max(...visibleEvents.map((e) => e.year || MIN_YEAR));
      const ratio = recencyRatio(newestYear, maxYear);

      // Brightness-scaled opacity, radius, and color
      const fillOpacity = lerp(BRIGHTNESS_FLOOR, BRIGHTNESS_CEIL, ratio);
      const radius = lerp(RADIUS_FLOOR, RADIUS_CEIL, ratio);
      const baseColor = EVENT_COLORS[visibleEvents[0].type] || "#6c7cff";
      const fillColor = brightenColor(baseColor, ratio);
      const borderOpacity = lerp(0.1, 0.4, ratio);

      // Era-colored border ring
      const era = getEra(newestYear);

      m.marker.setRadius(Math.min(radius + visibleEvents.length * 0.8, RADIUS_CEIL + 2));
      m.marker.setStyle({
        fillColor,
        fillOpacity,
        color: era.color,
        weight: 2,
        opacity: lerp(0.3, 1, ratio),
      });

      // Update popup
      const popupHtml = buildPlacePopup(visibleEvents[0].place, visibleEvents);
      m.marker.setPopupContent(popupHtml);
    } else {
      m.marker.setStyle({ fillOpacity: 0.03, opacity: 0.03 });
      m.marker.setRadius(RADIUS_FLOOR);
    }
  }

  // ── Arcs: temporal brightness + thickness ──
  for (const a of MAP_ARCS) {
    const personOk = filterPersonId === "all" || a.personId === filterPersonId;
    const yearOk = !a.toYear || a.toYear <= maxYear;
    const visible = personOk && yearOk;

    if (visible) {
      const ratio = recencyRatio(a.toYear, maxYear);
      const opacity = lerp(BRIGHTNESS_FLOOR, 0.8, ratio);
      const weight = lerp(WEIGHT_FLOOR, WEIGHT_CEIL, ratio);
      const baseColor = getPersonColor(a.personId);
      const color = brightenColor(baseColor, ratio);

      a.polyline.setStyle({ opacity, weight, color });
      a._arcWeight = weight;
      a._arcOpacity = opacity;
      if (a.hitArea) a.hitArea.setStyle({ weight: Math.max(weight * 4, 16) });
      a.arrowHead.setStyle({
        fillColor: color,
        fillOpacity: lerp(BRIGHTNESS_FLOOR, 0.9, ratio),
        opacity: lerp(0.2, 1, ratio),
        radius: lerp(2, 4, ratio),
      });
      if (a.boat) {
        if (MAP_ANIMATING && a.fromYear && a.toYear && a.toYear > a.fromYear) {
          // Glide from origin to port across the crossing's year span.
          if (maxYear < a.fromYear) {
            a.boat.setOpacity(0);
          } else {
            const t = Math.max(0, Math.min(1, (maxYear - a.fromYear) / (a.toYear - a.fromYear)));
            a.boat.setLatLng(pointAlong(a.latlngs, t));
            a.boat.setOpacity(1);
          }
        } else {
          a.boat.setLatLng(a.boatBase);
          a.boat.setOpacity(lerp(0.4, 1, ratio));
        }
      }
    } else {
      a.polyline.setStyle({ opacity: 0.03, weight: WEIGHT_FLOOR });
      if (a.hitArea) a.hitArea.setStyle({ weight: 0 });
      a.arrowHead.setStyle({ fillOpacity: 0.03, opacity: 0.03 });
      a.boat?.setOpacity(0.05);
    }
  }

  // ── Photo markers: show/hide based on year + person filter ──
  // Rebuild photo markers with filtered events
  const filteredPhotoEvents = MAP_ALL_EVENTS.filter(e => {
    if (e.type !== "photo") return false;
    const yearOk = !e.year || e.year <= maxYear;
    const personOk = filterPersonId === "all" || e.personId === filterPersonId;
    return yearOk && personOk;
  });
  plotPhotoMarkers(filteredPhotoEvents);
}

export function populateMapFilter(events) {
  const select = document.getElementById("map-person-filter");
  // Clear existing options except "Everyone"
  while (select.options.length > 1) select.remove(1);

  // Only include people who have visible map events
  const src = events || MAP_ALL_EVENTS;
  const peopleWithEvents = new Set(src.map((e) => e.personId));
  const sorted = Object.values(S.PEOPLE_MAP)
    .filter((p) => peopleWithEvents.has(p.id))
    .sort((a, b) => a.fullName.localeCompare(b.fullName));

  for (const p of sorted) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.fullName;
    select.appendChild(opt);
  }
}

export function setArcFlowAnimation(enabled) {
  for (const a of MAP_ARCS) {
    const el = a.polyline.getElement?.();
    if (el) {
      if (enabled) {
        el.classList.add("arc-flowing");
      } else {
        el.classList.remove("arc-flowing");
      }
    }
  }
}

export function toggleMapAnimation() {
  const btn = document.getElementById("map-play");
  const slider = document.getElementById("map-time-slider");
  const yearEndLabel = document.getElementById("slider-year-end");
  const badge = document.getElementById("map-year-badge");

  if (mapAnimTimer) {
    // Stop
    clearInterval(mapAnimTimer);
    mapAnimTimer = null;
    MAP_ANIMATING = false;
    btn.classList.remove("playing");
    btn.innerHTML = "&#9654;";
    setArcFlowAnimation(false);
    badge?.classList.remove("visible");
    updateMapForYear(parseInt(slider.value));  // settle boats back to rest
    return;
  }

  // Start from earliest year
  MAP_ANIMATING = true;
  slider.value = MIN_YEAR;
  yearEndLabel.textContent = MIN_YEAR;
  updateMapForYear(MIN_YEAR);
  btn.classList.add("playing");
  btn.innerHTML = "&#9646;&#9646;";
  setArcFlowAnimation(true);
  badge?.classList.add("visible");

  mapAnimTimer = setInterval(() => {
    // Step faster for wider year ranges (roughly constant animation duration ~6s)
    const totalYears = MAX_YEAR - MIN_YEAR;
    const step = Math.max(1, Math.round(totalYears / 150));
    let year = parseInt(slider.value) + step;
    if (year > MAX_YEAR) {
      clearInterval(mapAnimTimer);
      mapAnimTimer = null;
      MAP_ANIMATING = false;
      btn.classList.remove("playing");
      btn.innerHTML = "&#9654;";
      setArcFlowAnimation(false);
      badge?.classList.remove("visible");
      slider.value = MAX_YEAR;
      yearEndLabel.textContent = MAX_YEAR;
      updateMapForYear(MAX_YEAR);  // settle boats at their ports
      return;
    }
    slider.value = year;
    yearEndLabel.textContent = year;
    updateMapForYear(year);
  }, 40);
}

// ═══════════════════════════════════════════════════════════════
// Stats Badge
// ═══════════════════════════════════════════════════════════════

export function updateStats() {
  const badge = document.getElementById("stats-badge");
  const n = S.DATA.people.length;

  // Compute year span
  const years = S.DATA.people.map((p) => p.birth_date ? parseInt(p.birth_date.substring(0, 4)) : null).filter(Boolean);
  const minYear = years.length ? Math.min(...years) : "?";
  const maxYear = years.length ? Math.max(...years) : "?";

  // Compute max generation depth
  const parentsOf = {};
  for (const r of S.DATA.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }
  const hasParent = new Set(Object.keys(parentsOf));
  const roots = S.DATA.people.filter((p) => !hasParent.has(p.id)).map((p) => p.id);
  const childrenOf = {};
  for (const r of S.DATA.relationships) {
    if (!childrenOf[r.parent_id]) childrenOf[r.parent_id] = new Set();
    childrenOf[r.parent_id].add(r.child_id);
  }
  function maxDepth(id, seen = new Set()) {
    if (seen.has(id)) return 0;
    seen.add(id);
    const kids = childrenOf[id] || new Set();
    let d = 0;
    for (const kid of kids) d = Math.max(d, maxDepth(kid, seen));
    return 1 + d;
  }
  let gens = 0;
  for (const r of roots) gens = Math.max(gens, maxDepth(r));

  badge.textContent = `${n} people · ${gens} generations · ${minYear}–${maxYear}`;
}

// ═══════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════


// ── Map legend toggle (collapsible, collapsed by default on small screens) ──
const _mapLegendToggle = document.getElementById("map-legend-toggle");
const _mapLegends = document.getElementById("map-legends");
if (_mapLegendToggle && _mapLegends) {
  if (window.matchMedia("(max-width: 768px)").matches) {
    _mapLegends.classList.add("collapsed");
    _mapLegendToggle.setAttribute("aria-expanded", "false");
  }
  _mapLegendToggle.addEventListener("click", () => {
    const collapsed = _mapLegends.classList.toggle("collapsed");
    _mapLegendToggle.setAttribute("aria-expanded", String(!collapsed));
  });
}
