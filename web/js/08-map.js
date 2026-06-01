// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

const GEOCODE = {
  // ── family layout ──
  "Odessa, Russia":                   [46.48, 30.73],
  "Kamunetz-Podolsk, Russia":         [48.68, 26.58],
  "Russia":                           [55.75, 37.62],
  "Russia / Poland":                  [52.23, 21.01],
  "Poland / Russia":                  [52.23, 21.01],
  "Romania":                          [44.43, 26.10],
  "USA":                              [39.83, -98.58],
  "Boston, MA":                       [42.36, -71.06],
  "Roxbury, MA":                      [42.33, -71.09],
  "Salem Street, Boston, MA":         [42.365, -71.056],
  "Cambridge, MA":                    [42.374, -71.11],
  "Harvard University":               [42.374, -71.117],
  "Harvard University, Cambridge, MA":[42.374, -71.117],
  "Boston Latin School, Boston, MA":  [42.34, -71.10],
  "Gainesville, FL":                  [29.65, -82.32],
  "Ocala, FL":                        [29.19, -82.14],
  "Vanguard High School, Ocala, FL":  [29.19, -82.15],
  "Minnesota":                        [44.98, -93.27],
  "Evansville, IN":                   [37.97, -87.56],
  "Signature School, Evansville, IN": [37.97, -87.56],
  "San Francisco, CA":                [37.77, -122.42],
  "New York, NY":                     [40.71, -74.01],
  "Yale University":                  [41.31, -72.93],
  // ── Canada ──
  "Toronto, Ontario":               [43.70, -79.42],
  "Ontario":                        [51.25, -85.32],
  "Canada":                         [56.13, -106.35],
  // ── Poland / Morocco ──
  "Poland":                         [52.23, 21.01],
  "Morocco":                        [31.79,  -7.09],
  // ── Longfellow / Parkinson / Walters family ──
  "Hennepin County, Minnesota":                   [44.97, -93.27],
  "Minneapolis, Hennepin County, Minnesota":      [44.98, -93.27],
  "Bloomington, Hennepin County, Minnesota":      [44.84, -93.30],
  "Bloomington, Minnesota":                       [44.84, -93.30],
  "Wright, Carlton County, Minnesota":            [46.66, -92.56],
  "Anoka, Anoka County, Minnesota":               [45.20, -93.39],
  "Ramsey County, Minnesota":                     [44.95, -93.13],
  "Riverside, St. Louis County, Minnesota":       [47.53, -92.18],
  "Truro, Franklin County, Ohio":                 [39.97, -83.03],
  "Belvidere, Jackson County, South Dakota":      [43.83, -101.27],
  "San Diego, San Diego County, California":      [32.72, -117.16],
  "Illinois":                                     [40.63, -89.40],
};

// Runtime geocode results fetched from the server (Nominatim + DB cache).
// Populated by prefetchGeocode() on page load; map rendering awaits this.
const GEOCODE_RUNTIME = {};
let _geocodeReady = Promise.resolve();

// Polling interval for background geocode resolution (ms)
const _GEOCODE_POLL_MS = 3000;
let _geocodePlacesArr = [];

async function prefetchGeocode() {
  const places = new Set();
  for (const p of DATA.people) {
    if (p.birth_place) places.add(p.birth_place);
    if (p.death_place) places.add(p.death_place);
  }
  for (const e of DATA.events || []) {
    if (e.place) places.add(e.place);
  }
  for (const u of DATA.unions || []) {
    if (u.union_place) places.add(u.union_place);
  }
  if (places.size === 0) return;
  _geocodePlacesArr = [...places];
  await _fetchGeocodeAndPoll(_geocodePlacesArr);
}

async function _fetchGeocodeAndPoll(places) {
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
    if (newResults && MAP) {
      // Clear existing markers and arcs before re-plotting
      for (const m of MAP_MARKERS) m.marker.remove();
      for (const a of MAP_ARCS) { a.polyline.remove(); if (a.arrowHead) a.arrowHead.remove(); }
      MAP_MARKERS = [];
      MAP_ARCS = [];
      buildMapEvents();
      plotMapMarkers(MAP_ALL_EVENTS);
      plotMigrationArcs(MAP_ALL_EVENTS);
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

function geocode(place) {
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

const EVENT_COLORS = {
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

let MAP = null;
let MAP_MARKERS = [];      // { marker, latlng, events: [{date, year, type, personId, desc, place}] }
let MAP_ARCS = [];         // { polyline, arrowHead, personId, fromYear, toYear }
let MAP_ALL_EVENTS = [];   // flat list of {date, year, type, personId, place, desc, latlng}
let mapAnimTimer = null;
// The slider/filter/play controls are static DOM elements; their listeners are
// wired once (renderMap can run repeatedly via refreshAllViews).
let _mapListenersWired = false;

// Temporal brightness constants (MIN_YEAR computed dynamically from data)
let MIN_YEAR = 1650;    // will be recalculated from actual data
let MAX_YEAR = 2026;    // will be recalculated from actual data
const BRIGHTNESS_FLOOR = 0.12;   // opacity for oldest events
const BRIGHTNESS_CEIL  = 1.0;    // opacity for newest events
const RADIUS_FLOOR     = 4;      // marker radius for oldest
const RADIUS_CEIL      = 13;     // marker radius for newest
const WEIGHT_FLOOR     = 1;      // arc thickness for oldest
const WEIGHT_CEIL      = 3.5;    // arc thickness for newest

/**
 * Era definitions — each event gets an era tint based on its year.
 * Used to color-code the time period on the map.
 */
const ERAS = [
  { label: "Colonial",      start: 0,    end: 1800, color: "#c9a84c" },
  { label: "Antebellum",    start: 1800, end: 1870, color: "#6a8fb5" },
  { label: "Immigration",   start: 1870, end: 1920, color: "#c05040" },
  { label: "Mid-Century",   start: 1920, end: 1970, color: "#3ea58e" },
  { label: "Modern",        start: 1970, end: 9999, color: "#8b7cff" },
];

function getEra(year) {
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
function recencyRatio(year, maxYear) {
  if (!year || !maxYear || maxYear <= MIN_YEAR) return 0.5;
  return Math.max(0, Math.min(1, (year - MIN_YEAR) / (maxYear - MIN_YEAR)));
}

/** Linearly interpolate between a and b by t ∈ [0,1] */
function lerp(a, b, t) { return a + (b - a) * t; }

/**
 * Brighten / saturate a hex color toward white based on ratio (0=dim, 1=full).
 * At ratio=0 we darken to ~35% brightness; at ratio=1 we return the original.
 */
function brightenColor(hex, ratio) {
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

function _computeMapFog() {
  // Compute fog distance from ORIGINAL_DATA so focus-mode filtering doesn't
  // cause ancestors/relatives to disappear from the map. Shared algorithm with
  // the tree layout via computeFogDistance (defined in 04-tree.js).
  return computeFogDistance(ORIGINAL_DATA || DATA);
}

function buildMapEvents() {
  MAP_ALL_EVENTS = [];

  // The map shows ALL geo data in the database. Fog level is stored on each
  // event for styling (opacity/size) but is NOT used to exclude events — the
  // map is a geographic overview across the entire dataset. Viewer-based
  // filtering (fog-of-war) is a tree-view concern only.
  const fog = _computeMapFog();

  function personFog(pid) {
    return fog[pid] !== undefined ? Math.min(fog[pid], 4) : 4;
  }

  // Use ORIGINAL_DATA so focus-mode filtering doesn't hide map locations
  const src = ORIGINAL_DATA || DATA;
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
      desc: `${personName(e.person_id)} — ${e.description || e.event_type}`,
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

async function renderMap() {
  await _geocodeReady;
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
  if (MAP) { MAP.remove(); MAP = null; }
  MAP_MARKERS = [];
  MAP_ARCS = [];

  MAP = L.map("map", {
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
  }).addTo(MAP);

  // Attribution (subtle)
  L.control.attribution({ prefix: false, position: "bottomright" })
    .addAttribution('&copy; <a href="https://carto.com/">CARTO</a>')
    .addTo(MAP);

  buildMapEvents();
  plotMapMarkers(MAP_ALL_EVENTS);
  plotPhotoMarkers(MAP_ALL_EVENTS);
  plotMigrationArcs(MAP_ALL_EVENTS);
  populateMapFilter();

  // Fit bounds
  const allLatLngs = MAP_ALL_EVENTS.map((e) => e.latlng);
  if (allLatLngs.length > 0) {
    MAP.fitBounds(allLatLngs, { padding: [50, 50], maxZoom: 6 });
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
    _mapListenersWired = true;
  }
}

function plotMapMarkers(events) {
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

  // Offset radius in degrees — small enough to look clustered, large enough to see
  const OFFSET_DEG = 0.15;

  for (const groups of Object.values(byCoord)) {
    const n = groups.length;
    groups.forEach((group, i) => {
      let markerLatLng = group.latlng;
      if (n > 1) {
        // Fan out in a circle around the original point
        const angle = (2 * Math.PI * i) / n - Math.PI / 2;
        const offsetLat = OFFSET_DEG * Math.sin(angle);
        const offsetLng = OFFSET_DEG * Math.cos(angle);
        markerLatLng = [group.latlng[0] + offsetLat, group.latlng[1] + offsetLng];
      }

      const newestYear = Math.max(...group.events.map((e) => e.year || MIN_YEAR));
      const ratio = recencyRatio(newestYear, MAX_YEAR);
      const primaryType = group.events[0].type;
      const baseColor = EVENT_COLORS[primaryType] || "#6c7cff";
      const fillColor = brightenColor(baseColor, ratio);
      const fillOpacity = lerp(BRIGHTNESS_FLOOR, BRIGHTNESS_CEIL, ratio);
      const radius = lerp(RADIUS_FLOOR, RADIUS_CEIL, ratio);
      const era = getEra(newestYear);

      const marker = L.circleMarker(markerLatLng, {
        radius: Math.min(radius + group.events.length * 0.5, RADIUS_CEIL + 2),
        fillColor,
        fillOpacity,
        color: era.color,
        weight: 2,
      }).addTo(MAP);

      marker.on("mouseover", (e) => {
        const primaryEvent = group.events[0];
        if (primaryEvent) {
          const containerPt = MAP.latLngToContainerPoint(e.latlng);
          const mapEl = document.getElementById("map");
          const mapRect = mapEl.getBoundingClientRect();
          showHovercardAt(primaryEvent.personId, mapRect.left + containerPt.x, mapRect.top + containerPt.y);
        }
      });
      marker.on("mouseout", () => { hideHovercard(); });

      marker.on("click", () => {
        const primaryEvent = group.events[0];
        if (primaryEvent) {
          showPersonPanel(primaryEvent.personId);
          router.navigate(`/map/person/${primaryEvent.personId}`);
        }
      });

      const popupHtml = buildPlacePopup(group.place, group.events);
      marker.bindPopup(popupHtml, { maxWidth: 300, maxHeight: 300 });

      MAP_MARKERS.push({
        marker,
        latlng: markerLatLng,
        origLatlng: group.latlng,
        events: group.events,
        placeKey: group.latlng.join(","),
      });
    });
  }
}

function buildPlacePopup(place, events) {
  let html = `<h4>${place}</h4>`;
  for (const e of events) {
    const year = e.year || "?";
    const dotColor = EVENT_COLORS[e.type] || "#6c7cff";
    const person = PEOPLE_MAP[e.personId];
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
      const p2 = PEOPLE_MAP[e.partner2Id];
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

// Photo thumbnail markers on map
let MAP_PHOTO_MARKERS = [];

function plotPhotoMarkers(events) {
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
        iconSize: [40, 40],
        iconAnchor: [20, 20],
      });
      const marker = L.marker(cluster.latlng, { icon }).addTo(MAP);
      marker.on("click", () => {
        openLightbox("/" + firstPhoto.photoPath, "", firstPhoto.photoPath);
      });
      MAP_PHOTO_MARKERS.push(marker);
    } else {
      // Cluster: show first photo with count badge
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-photo-marker" style="position:relative"><img src="/${firstPhoto.photoPath}" alt="" /><span class="map-photo-count">${count}</span></div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
      });
      const marker = L.marker(cluster.latlng, { icon }).addTo(MAP);

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
const PERSON_COLORS = {};
const ARC_PALETTE = [
  "#6c7cff", "#ff6b8a", "#f5a623", "#4cd964", "#b066e0",
  "#e74c3c", "#4a90d9", "#d94a8c", "#50e3c2", "#f8e71c",
];
let arcColorIdx = 0;

function getPersonColor(personId) {
  if (!PERSON_COLORS[personId]) {
    PERSON_COLORS[personId] = ARC_PALETTE[arcColorIdx % ARC_PALETTE.length];
    arcColorIdx++;
  }
  return PERSON_COLORS[personId];
}

function plotMigrationArcs(events) {
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
        waypoints.push({ latlng: e.latlng, key, year: e.year, date: e.date });
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
      const polyline = L.polyline(latlngs, {
        color: arcColor,
        weight: arcWeight,
        opacity: arcOpacity,
        dashArray: "6,4",
      }).addTo(MAP);

      // Arrow decorator at the end
      const arrowHead = L.circleMarker(to.latlng, {
        radius: lerp(2, 4, ratio),
        fillColor: arcColor,
        fillOpacity: lerp(BRIGHTNESS_FLOOR, 0.9, ratio),
        color: arcColor,
        weight: 1,
      }).addTo(MAP);

      // Tooltip on hover
      polyline.bindTooltip(
        `${personName(personId)}: ${from.year || "?"} → ${to.year || "?"}`,
        { sticky: true, className: "arc-tooltip" }
      );

      MAP_ARCS.push({
        polyline,
        arrowHead,
        personId,
        fromYear: from.year,
        toYear: to.year,
      });
    }
  }
}

function curvedPath(from, to) {
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

function updateMapForYear(maxYear) {
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
      a.arrowHead.setStyle({
        fillColor: color,
        fillOpacity: lerp(BRIGHTNESS_FLOOR, 0.9, ratio),
        opacity: lerp(0.2, 1, ratio),
        radius: lerp(2, 4, ratio),
      });
    } else {
      a.polyline.setStyle({ opacity: 0.03, weight: WEIGHT_FLOOR });
      a.arrowHead.setStyle({ fillOpacity: 0.03, opacity: 0.03 });
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

function populateMapFilter() {
  const select = document.getElementById("map-person-filter");
  // Clear existing options except "Everyone"
  while (select.options.length > 1) select.remove(1);

  // Only include people who have map events
  const peopleWithEvents = new Set(MAP_ALL_EVENTS.map((e) => e.personId));
  const sorted = Object.values(PEOPLE_MAP)
    .filter((p) => peopleWithEvents.has(p.id))
    .sort((a, b) => a.fullName.localeCompare(b.fullName));

  for (const p of sorted) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.fullName;
    select.appendChild(opt);
  }
}

function setArcFlowAnimation(enabled) {
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

function toggleMapAnimation() {
  const btn = document.getElementById("map-play");
  const slider = document.getElementById("map-time-slider");
  const yearEndLabel = document.getElementById("slider-year-end");

  if (mapAnimTimer) {
    // Stop
    clearInterval(mapAnimTimer);
    mapAnimTimer = null;
    btn.classList.remove("playing");
    btn.innerHTML = "&#9654;";
    setArcFlowAnimation(false);
    return;
  }

  // Start from earliest year
  slider.value = MIN_YEAR;
  yearEndLabel.textContent = MIN_YEAR;
  updateMapForYear(MIN_YEAR);
  btn.classList.add("playing");
  btn.innerHTML = "&#9646;&#9646;";
  setArcFlowAnimation(true);

  mapAnimTimer = setInterval(() => {
    // Step faster for wider year ranges (roughly constant animation duration ~6s)
    const totalYears = MAX_YEAR - MIN_YEAR;
    const step = Math.max(1, Math.round(totalYears / 150));
    let year = parseInt(slider.value) + step;
    if (year > MAX_YEAR) {
      clearInterval(mapAnimTimer);
      mapAnimTimer = null;
      btn.classList.remove("playing");
      btn.innerHTML = "&#9654;";
      setArcFlowAnimation(false);
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

function updateStats() {
  const badge = document.getElementById("stats-badge");
  const n = DATA.people.length;

  // Compute year span
  const years = DATA.people.map((p) => p.birth_date ? parseInt(p.birth_date.substring(0, 4)) : null).filter(Boolean);
  const minYear = years.length ? Math.min(...years) : "?";
  const maxYear = years.length ? Math.max(...years) : "?";

  // Compute max generation depth
  const parentsOf = {};
  for (const r of DATA.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }
  const hasParent = new Set(Object.keys(parentsOf));
  const roots = DATA.people.filter((p) => !hasParent.has(p.id)).map((p) => p.id);
  const childrenOf = {};
  for (const r of DATA.relationships) {
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

