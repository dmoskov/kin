// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

let LANES = [];

let LANE_CACHE = {};  // personId → lane id

// Auto-generate lane colors (muted, distinct)
const _AUTO_LANE_COLORS = [
  "#b33a3a", "#2e6ca4", "#d4a843", "#4a7c59",
  "#9c4a70", "#6b5b95", "#c4956a", "#3a8b8b",
];

/**
 * Ensure CENTER_ID_A and CENTER_ID_B point to valid people.
 * If they don't exist in PEOPLE_MAP, auto-detect the best center couple.
 */
function _resolveCenterIds() {
  if (!DATA) return;
  if (!CENTER_ID_A || !PEOPLE_MAP[CENTER_ID_A]) {
    const childCount = {};
    for (const r of DATA.relationships) {
      childCount[r.parent_id] = (childCount[r.parent_id] || 0) + 1;
    }
    const unionCount = {};
    for (const u of DATA.unions) {
      unionCount[u.partner1_id] = (unionCount[u.partner1_id] || 0) + 1;
      unionCount[u.partner2_id] = (unionCount[u.partner2_id] || 0) + 1;
    }
    const best = Object.values(PEOPLE_MAP).sort((a, b) =>
      ((childCount[b.id] || 0) + (unionCount[b.id] || 0)) -
      ((childCount[a.id] || 0) + (unionCount[a.id] || 0))
    )[0];
    if (best) CENTER_ID_A = best.id;
  }
  if (!CENTER_ID_B || !PEOPLE_MAP[CENTER_ID_B]) {
    const u = DATA.unions.find(u => u.partner1_id === CENTER_ID_A || u.partner2_id === CENTER_ID_A);
    if (u) CENTER_ID_B = u.partner1_id === CENTER_ID_A ? u.partner2_id : u.partner1_id;
  }
}

/**
 * Auto-detect lanes when CONFIG.lanes is not set.
 *
 * Strategy: find the center couple, trace each partner's parents to create
 * one lane per parent line (typically 4 lanes for 4 grandparents). If no
 * center couple, find root ancestors and group by surname.
 */
function _autoDetectLanes() {
  if (!DATA || DATA.people.length < 2) return [];

  _resolveCenterIds();

  const parentsOf = {};
  for (const r of DATA.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }

  // Find center couple
  const centerA = CENTER_ID_A && PEOPLE_MAP[CENTER_ID_A] ? CENTER_ID_A : null;
  const centerB = CENTER_ID_B && PEOPLE_MAP[CENTER_ID_B] ? CENTER_ID_B : null;

  if (centerA || centerB) {
    // Build lanes from each parent of each center person
    const lanes = [];
    const centerPeople = [centerA, centerB].filter(Boolean);

    for (const centerId of centerPeople) {
      const parents = parentsOf[centerId] || [];
      if (parents.length > 0) {
        // One lane per parent (grandparent line)
        for (const parentId of parents) {
          const p = PEOPLE_MAP[parentId];
          if (!p) continue;
          const surname = p.surname || p.given_name || parentId;
          lanes.push({
            id: parentId,
            label: surname,
            rootIds: [parentId],
            color: _AUTO_LANE_COLORS[lanes.length % _AUTO_LANE_COLORS.length],
          });
        }
      } else {
        // Center person has no parents — make them a lane root
        const p = PEOPLE_MAP[centerId];
        const surname = p?.surname || p?.given_name || centerId;
        lanes.push({
          id: centerId,
          label: surname,
          rootIds: [centerId],
          color: _AUTO_LANE_COLORS[lanes.length % _AUTO_LANE_COLORS.length],
        });
      }
    }
    if (lanes.length > 0) return lanes;
  }

  // Fallback: group root ancestors (no parents) by surname
  const roots = DATA.people.filter(p => !parentsOf[p.id] || parentsOf[p.id].length === 0);
  const bySurname = {};
  for (const r of roots) {
    const key = r.surname || "Unknown";
    if (!bySurname[key]) bySurname[key] = [];
    bySurname[key].push(r.id);
  }

  const surnames = Object.keys(bySurname).sort();
  // Only create lanes if there are 2-8 surname groups; otherwise it's too many/too few
  if (surnames.length < 2 || surnames.length > 8) return [];

  return surnames.map((surname, i) => ({
    id: `auto-${surname.toLowerCase().replace(/\s+/g, "-")}`,
    label: surname,
    rootIds: bySurname[surname],
    color: _AUTO_LANE_COLORS[i % _AUTO_LANE_COLORS.length],
  }));
}

function buildLaneCache() {
  LANE_CACHE = {};
  if (!DATA) return;

  // Auto-detect lanes if none configured
  if (LANES.length === 0) {
    const autoLanes = _autoDetectLanes();
    if (autoLanes.length > 0) LANES = autoLanes;
  }

  // Build parent → children and child → parents lookups
  const childrenOf = {};
  const parentsOf = {};
  for (const r of DATA.relationships) {
    if (!childrenOf[r.parent_id]) childrenOf[r.parent_id] = [];
    childrenOf[r.parent_id].push(r.child_id);
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }

  // Phase 1: Build bloodline-only lanes (parent-child, no partners)
  // First pass: compute bloodline sets for all lanes
  const laneBloodlines = [];
  for (const lane of LANES) {
    const bloodline = new Set();
    const roots = lane.rootIds || (lane.rootId ? [lane.rootId] : []);

    const resolvedRoots = [];
    for (let rootId of roots) {
      // Fuzzy root resolution: try exact ID, then fall back to name match
      if (!PEOPLE_MAP[rootId]) {
        const parts = rootId.split("-");
        const surname = parts[parts.length - 1];
        const given = parts.slice(0, -1).join(" ");
        const match = Object.values(PEOPLE_MAP).find(p =>
          p.given_name?.toLowerCase() === given && (p.surname || "").toLowerCase().includes(surname)
        );
        if (match) rootId = match.id;
      }
      resolvedRoots.push(rootId);

      // Trace ancestors upward from root (include them in lane, but
      // do NOT use them as starting points for descendant expansion)
      const ancestorStack = [rootId];
      while (ancestorStack.length > 0) {
        const pid = ancestorStack.pop();
        if (bloodline.has(pid)) continue;
        bloodline.add(pid);
        for (const parent of (parentsOf[pid] || [])) {
          ancestorStack.push(parent);
        }
      }
    }

    // Trace descendants downward ONLY from the lane roots (not all ancestors)
    // This prevents pulling in cousins/siblings of distant ancestors
    const descStack = [...resolvedRoots];
    const visited = new Set(resolvedRoots);
    while (descStack.length > 0) {
      const pid = descStack.pop();
      bloodline.add(pid);
      for (const child of (childrenOf[pid] || [])) {
        if (!visited.has(child)) {
          visited.add(child);
          bloodline.add(child);
          descStack.push(child);
        }
      }
    }

    laneBloodlines.push({ lane, bloodline });
  }

  // Second pass: assign each person to the lane where they appear in the
  // fewest bloodlines (most specific). Ties broken by lane order.
  const personLanes = {}; // personId → [lane indices]
  for (let i = 0; i < laneBloodlines.length; i++) {
    for (const pid of laneBloodlines[i].bloodline) {
      if (!personLanes[pid]) personLanes[pid] = [];
      personLanes[pid].push(i);
    }
  }

  // Assign: if a person belongs to exactly one bloodline, that's their lane.
  // If they belong to multiple (shared descendant), pick the lane whose
  // bloodline is smallest (most specific to that family line).
  for (const [pid, indices] of Object.entries(personLanes)) {
    if (indices.length === 1) {
      LANE_CACHE[pid] = laneBloodlines[indices[0]].lane.id;
    } else {
      // Pick lane with smallest bloodline (most specific)
      let best = indices[0];
      for (const i of indices) {
        if (laneBloodlines[i].bloodline.size < laneBloodlines[best].bloodline.size) best = i;
      }
      LANE_CACHE[pid] = laneBloodlines[best].lane.id;
    }
  }

  // Debug: log lane stats
  console.log("[Lanes] Active:", LANES.map(l => `${l.label}(${l.id})`));
  for (const { lane, bloodline } of laneBloodlines) {
    const names = [...bloodline].slice(0, 5).map(id => PEOPLE_MAP[id]?.fullName || id);
    console.log(`  ${lane.label}: ${bloodline.size} people (sample: ${names.join(", ")})`);
  }
  const unassigned = DATA.people.filter(p => !LANE_CACHE[p.id]);
  if (unassigned.length > 0) {
    console.log(`  Unassigned: ${unassigned.length} people:`, unassigned.slice(0, 10).map(p => p.given_name + " " + (p.surname || "")));
  }

  // Phase 2: Assign partners to their spouse's lane (unions only, iterate until stable)
  let changed = true;
  while (changed) {
    changed = false;
    for (const u of DATA.unions) {
      if (LANE_CACHE[u.partner1_id] && !LANE_CACHE[u.partner2_id]) {
        LANE_CACHE[u.partner2_id] = LANE_CACHE[u.partner1_id];
        changed = true;
      }
      if (LANE_CACHE[u.partner2_id] && !LANE_CACHE[u.partner1_id]) {
        LANE_CACHE[u.partner1_id] = LANE_CACHE[u.partner2_id];
        changed = true;
      }
    }
  }
}

function assignLane(personId) {
  return LANE_CACHE[personId] || null;
}

// Lane colors for auto-computed lanes (cycling)
const LANE_COLORS = ["var(--male)", "var(--event-custom)", "var(--event-education)", "var(--event-birth)",
                     "var(--female)", "var(--union)", "var(--event-career)", "var(--accent)"];

// Auto-compute lanes from a center couple's grandparents
function autoComputeLanes(centerA, centerB) {
  if (!DATA) return;

  const parentsOf = {};
  for (const r of DATA.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }

  // Collect grandparents (or parents as fallback) for each center person
  function getGrandparents(personId) {
    const parents = parentsOf[personId] || [];
    const gps = [];
    for (const pid of parents) {
      const gpList = parentsOf[pid] || [];
      if (gpList.length > 0) {
        for (const gp of gpList) gps.push(gp);
      } else {
        // No grandparents — use parent as lane root
        gps.push(pid);
      }
    }
    // If no parents at all, use the person themselves
    return gps.length > 0 ? gps : [personId];
  }

  const gpsA = getGrandparents(centerA);
  const gpsB = centerB && centerB !== centerA ? getGrandparents(centerB) : [];

  // Deduplicate and build lanes
  const seen = new Set();
  const lanes = [];
  let colorIdx = 0;

  for (const gp of [...gpsA, ...gpsB]) {
    if (seen.has(gp)) continue;
    seen.add(gp);
    const person = PEOPLE_MAP[gp];
    const label = person ? (person.surname || person.given_name || "Unknown") : "Unknown";
    lanes.push({
      id: `auto-${gp}`,
      label,
      rootIds: [gp],
      color: LANE_COLORS[colorIdx % LANE_COLORS.length],
    });
    colorIdx++;
  }

  console.log("[autoComputeLanes] centerA:", centerA, "centerB:", centerB);
  console.log("[autoComputeLanes] grandparents A:", gpsA.map(id => PEOPLE_MAP[id]?.fullName || id));
  console.log("[autoComputeLanes] grandparents B:", gpsB.map(id => PEOPLE_MAP[id]?.fullName || id));
  console.log("[autoComputeLanes] lanes:", lanes.map(l => `${l.label} (root: ${l.rootIds})`));

  LANES = lanes;
  buildLaneCache();
  _updateHeaderFromLanes();
}

/**
 * Set the page title from auto-detected lane labels when no familyName is
 * configured.  Produces e.g. "Smith · Jones · Brown · Wilson".
 * Only runs once on initial load; updateDynamicHeader overrides when a
 * viewer is explicitly selected.
 */
function _updateHeaderFromLanes() {
  if (CONFIG.familyName) return; // explicit config takes priority
  if (LANES.length === 0) return;
  const titleEl = document.getElementById("family-title");
  if (!titleEl) return;
  titleEl.textContent = LANES.map(l => l.label).join(" \u00b7 ");
}

