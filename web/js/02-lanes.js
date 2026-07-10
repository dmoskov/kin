// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";


let LANE_CACHE = {};  // personId → lane id

/**
 * Ensure S.CENTER_ID_A and S.CENTER_ID_B point to valid people.
 * If they don't exist in S.PEOPLE_MAP, auto-detect the best center couple.
 */
export function _resolveCenterIds() {
  if (!S.DATA) return;
  if (!S.CENTER_ID_A || !S.PEOPLE_MAP[S.CENTER_ID_A]) {
    const childCount = {};
    for (const r of S.DATA.relationships) {
      childCount[r.parent_id] = (childCount[r.parent_id] || 0) + 1;
    }
    const unionCount = {};
    for (const u of S.DATA.unions) {
      unionCount[u.partner1_id] = (unionCount[u.partner1_id] || 0) + 1;
      unionCount[u.partner2_id] = (unionCount[u.partner2_id] || 0) + 1;
    }
    const best = Object.values(S.PEOPLE_MAP).sort((a, b) =>
      ((childCount[b.id] || 0) + (unionCount[b.id] || 0)) -
      ((childCount[a.id] || 0) + (unionCount[a.id] || 0))
    )[0];
    if (best) S.CENTER_ID_A = best.id;
  }
  if (!S.CENTER_ID_B || !S.PEOPLE_MAP[S.CENTER_ID_B]) {
    const u = S.DATA.unions.find(u => u.partner1_id === S.CENTER_ID_A || u.partner2_id === S.CENTER_ID_A);
    if (u) S.CENTER_ID_B = u.partner1_id === S.CENTER_ID_A ? u.partner2_id : u.partner1_id;
  }
}

export function buildLaneCache() {
  LANE_CACHE = {};
  if (!S.DATA) return;

  // Build parent → children and child → parents lookups
  const childrenOf = {};
  const parentsOf = {};
  for (const r of S.DATA.relationships) {
    if (!childrenOf[r.parent_id]) childrenOf[r.parent_id] = [];
    childrenOf[r.parent_id].push(r.child_id);
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }

  // Phase 1: Build bloodline-only lanes (parent-child, no partners)
  // First pass: compute bloodline sets for all lanes
  const laneBloodlines = [];
  for (const lane of S.LANES) {
    const bloodline = new Set();
    const roots = lane.rootIds || (lane.rootId ? [lane.rootId] : []);

    const resolvedRoots = [];
    for (let rootId of roots) {
      if (!rootId) continue; // no root (e.g. a center person with no partner)
      // Fuzzy root resolution: try exact ID, then fall back to name match
      if (!S.PEOPLE_MAP[rootId]) {
        const parts = rootId.split("-");
        const surname = parts[parts.length - 1];
        const given = parts.slice(0, -1).join(" ");
        const match = Object.values(S.PEOPLE_MAP).find(p =>
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
  console.log("[Lanes] Active:", S.LANES.map(l => `${l.label}(${l.id})`));
  for (const { lane, bloodline } of laneBloodlines) {
    const names = [...bloodline].slice(0, 5).map(id => S.PEOPLE_MAP[id]?.fullName || id);
    console.log(`  ${lane.label}: ${bloodline.size} people (sample: ${names.join(", ")})`);
  }
  const unassigned = S.DATA.people.filter(p => !LANE_CACHE[p.id]);
  if (unassigned.length > 0) {
    console.log(`  Unassigned: ${unassigned.length} people:`, unassigned.slice(0, 10).map(p => p.given_name + " " + (p.surname || "")));
  }

  // Phase 2: Assign partners to their spouse's lane (unions only, iterate until stable)
  let changed = true;
  while (changed) {
    changed = false;
    for (const u of S.DATA.unions) {
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

export function assignLane(personId) {
  return LANE_CACHE[personId] || null;
}

// Lane colors for auto-computed lanes (cycling)
export const LANE_COLORS = ["var(--male)", "var(--event-custom)", "var(--event-education)", "var(--event-birth)",
                     "var(--female)", "var(--union)", "var(--event-career)", "var(--accent)"];

// Auto-compute lanes from a center couple's grandparents
export function autoComputeLanes(centerA, centerB) {
  if (!S.DATA) return;

  const parentsOf = {};
  for (const r of S.DATA.relationships) {
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
    // If no parents at all, use the person themselves (unless there's no person)
    return gps.length > 0 ? gps : personId ? [personId] : [];
  }

  const gpsA = getGrandparents(centerA);
  const gpsB = centerB && centerB !== centerA ? getGrandparents(centerB) : [];

  // Deduplicate and build lanes
  const seen = new Set();
  const lanes = [];
  let colorIdx = 0;

  const fromA = new Set(gpsA);
  for (const gp of [...gpsA, ...gpsB]) {
    if (!gp || seen.has(gp)) continue;
    seen.add(gp);
    const person = S.PEOPLE_MAP[gp];
    let label = person ? (person.surname || person.given_name || "") : "";
    if (!label) {
      // Nameless lane root: label the branch by which side of the center
      // couple it belongs to, so chips never read as bare "Unknown".
      const center = S.PEOPLE_MAP[fromA.has(gp) ? centerA : centerB];
      const centerName = center && (center.given_name || center.fullName);
      label = centerName ? `${centerName}'s side` : "Unknown";
    }
    lanes.push({
      id: `auto-${gp}`,
      label,
      rootIds: [gp],
      color: LANE_COLORS[colorIdx % LANE_COLORS.length],
    });
    colorIdx++;
  }

  console.log("[autoComputeLanes] centerA:", centerA, "centerB:", centerB);
  console.log("[autoComputeLanes] grandparents A:", gpsA.map(id => S.PEOPLE_MAP[id]?.fullName || id));
  console.log("[autoComputeLanes] grandparents B:", gpsB.map(id => S.PEOPLE_MAP[id]?.fullName || id));
  console.log("[autoComputeLanes] lanes:", lanes.map(l => `${l.label} (root: ${l.rootIds})`));

  S.LANES = lanes;
  buildLaneCache();
  _updateHeaderFromLanes();
}

// ── Sublines: which ancestral sub-families a person belongs to ──────────
// Heraldry-style membership for the tree view. Each of the center couple's
// grandparent couples founds a "subline" (Siegel, Kleinberg, …); a person
// carries a subline's glyph when they are blood kin to it — an ancestor,
// a descendant, or collateral blood (a great-uncle is still a Siegel). The
// glyphs therefore accumulate down the generations: the center couple's
// children carry every subline of both sides. Married-in spouses carry
// none — a bare card is itself the "not blood family" signal.
export const SUBLINE_GLYPHS = ["◆", "●", "▲", "■", "✦", "⬢"];
// Dedicated subline palette (not the gender pink/blue, not the lane vars):
// validated for lightness, chroma, CVD separation and contrast against both
// theme surfaces (#f5f0e8 light / #1a1714 dark); the glyph shapes above are
// the color-independent secondary encoding.
export const SUBLINE_COLORS = ["#0f9482", "#b34a32", "#7d5ba6", "#b8790f", "#3b74c9", "#a34d7c"];

export function computeSublines() {
  if (!S.DATA) return { sublines: [], byPerson: {} };

  const parentsOf = {};
  const childrenOf = {};
  for (const r of S.DATA.relationships) {
    (parentsOf[r.child_id] ||= []).push(r.parent_id);
    (childrenOf[r.parent_id] ||= []).push(r.child_id);
  }
  const partnersOf = {};
  for (const u of S.DATA.unions) {
    (partnersOf[u.partner1_id] ||= []).push(u.partner2_id);
    (partnersOf[u.partner2_id] ||= []).push(u.partner1_id);
  }

  // Root couples: each center partner's grandparent couples. A parent with
  // no parents of their own roots a subline directly (their surname still
  // names a family) — same fallback as autoComputeLanes.
  const roots = [];
  const seenRoot = new Set();
  for (const centerPid of [S.CENTER_ID_A, S.CENTER_ID_B]) {
    if (!centerPid) continue;
    for (const par of parentsOf[centerPid] || []) {
      const gps = (parentsOf[par] || []).filter((g) => S.PEOPLE_MAP[g]);
      const groups = [];
      const used = new Set();
      for (const g of gps) {
        if (used.has(g)) continue;
        const mate = (partnersOf[g] || []).find((m) => gps.includes(m) && m !== g);
        used.add(g);
        if (mate) used.add(mate);
        groups.push(mate ? [g, mate] : [g]);
      }
      if (groups.length === 0 && S.PEOPLE_MAP[par]) groups.push([par]);
      for (const ids of groups) {
        const key = [...ids].sort().join("|");
        if (seenRoot.has(key)) continue;
        seenRoot.add(key);
        roots.push({ ids, via: par });
      }
    }
  }

  const sublines = [];
  const byPerson = {};
  roots.forEach((root, idx) => {
    // Blood members: the root couple, all their ancestors, and every
    // descendant of any of those.
    const up = new Set();
    const upStack = [...root.ids];
    while (upStack.length) {
      const pid = upStack.pop();
      if (up.has(pid)) continue;
      up.add(pid);
      for (const p of parentsOf[pid] || []) upStack.push(p);
    }
    const members = new Set(up);
    const downStack = [...up];
    while (downStack.length) {
      const pid = downStack.pop();
      for (const kid of childrenOf[pid] || []) {
        if (!members.has(kid)) {
          members.add(kid);
          downStack.push(kid);
        }
      }
    }

    // Label: prefer the root partner whose surname the connecting parent
    // carries (Abraham SIEGEL over Ida Tocher when the line runs through
    // Jack Siegel), then the male partner, then whoever is first.
    const people = root.ids.map((id) => S.PEOPLE_MAP[id]).filter(Boolean);
    const viaSurname = (S.PEOPLE_MAP[root.via]?.surname || "").toLowerCase();
    const namer =
      people.find((p) => p.surname && p.surname.toLowerCase() === viaSurname) ||
      people.find((p) => p.gender === "male") ||
      people[0];
    const label = namer?.surname || namer?.given_name || "Family";

    const color = SUBLINE_COLORS[idx % SUBLINE_COLORS.length];

    for (const pid of members) (byPerson[pid] ||= []).push(idx);
    sublines.push({ label, color, glyph: SUBLINE_GLYPHS[idx % SUBLINE_GLYPHS.length] });
  });

  return { sublines, byPerson };
}

/**
 * Set the page title from auto-detected lane labels when no familyName is
 * configured.  Produces e.g. "Smith · Jones · Brown · Wilson".
 * Only runs once on initial load; updateDynamicHeader overrides when a
 * viewer is explicitly selected.
 */
export function _updateHeaderFromLanes() {
  if (S.CONFIG.familyName) return; // explicit config takes priority
  if (S.LANES.length === 0) return;
  const titleEl = document.getElementById("family-title");
  if (!titleEl) return;
  // Drop placeholder labels so a tree with unnamed grandparents never renders
  // a serif headline of "Unknown \u00b7 Unknown" (or "John's side \u00b7 \u2026").
  // Fall back to a calm default.
  const labels = S.LANES.map(l => l.label).filter(l => l && l !== "Unknown" && !l.endsWith("'s side"));
  titleEl.textContent = labels.length ? labels.join(" \u00b7 ") : "Family Tree";
}

