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
// children carry every subline of both sides. Married-in spouses found a
// MINOR subline of their own (rooted at their parents when shown, else at
// themselves): their in-law family cluster shares it and their children
// inherit it — the "new blood" half of every blended line. Minor lines are
// kept out of the legend.
// Dedicated subline palette (not the gender pink/blue, not the lane vars):
// validated for lightness, chroma, CVD separation and contrast against both
// theme surfaces (#f5f0e8 light / #1a1714 dark); the legend's labeled dots
// are the fallback naming when color alone is ambiguous.
export const SUBLINE_COLORS = [
  "#0f9482", "#b34a32", "#3b74c9", "#b8790f", "#7d5ba6", "#4f9433",
  "#b8478f", "#1990bd", "#c96a2b", "#5f5fd3", "#ad8508", "#a34d7c",
  "#1f9663", "#c4574e", "#5578cf", "#9c6f1d", "#9a6fc0", "#5d8c1d",
  "#d4589e", "#b06a3c", "#0c93ab", "#7a6fd8", "#7d8a10", "#c14a68",
];

export function computeSublines(depth = 2) {
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

  // Root couples sit `depth` generations above the center couple (2 =
  // grandparents, 3 = great-grandparents, …). A line that ends early roots
  // at its deepest person instead — their surname still names a family —
  // so every blood line founds a subline regardless of how far back it goes.
  const groupCouples = (pids) => {
    const groups = [];
    const used = new Set();
    for (const g of pids) {
      if (used.has(g)) continue;
      const mate = (partnersOf[g] || []).find((m) => pids.includes(m) && m !== g);
      used.add(g);
      if (mate) used.add(mate);
      groups.push(mate ? [g, mate] : [g]);
    }
    return groups;
  };
  const rootsAbove = (pid, gensUp) => {
    const pars = (parentsOf[pid] || []).filter((g) => S.PEOPLE_MAP[g]);
    if (pars.length === 0) return [{ ids: [pid], via: pid }];
    if (gensUp === 1) return groupCouples(pars).map((ids) => ({ ids, via: pid }));
    const out = [];
    for (const par of pars) out.push(...rootsAbove(par, gensUp - 1));
    return out;
  };
  const roots = [];
  const seenRoot = new Set();
  for (const centerPid of [S.CENTER_ID_A, S.CENTER_ID_B]) {
    if (!centerPid || !(parentsOf[centerPid] || []).length) continue;
    for (const root of rootsAbove(centerPid, Math.max(2, depth))) {
      const key = [...root.ids].sort().join("|");
      if (seenRoot.has(key)) continue;
      seenRoot.add(key);
      roots.push(root);
    }
  }

  const sublines = [];
  const byPerson = {};

  // Color assignment: major lines take the validated palette in order (its
  // pairwise adjacency was checked). Minor lines pick greedily — the unused
  // color farthest in hue from everything assigned so far — so a married-in
  // spouse's new color can't be a near-twin of the blood family they joined
  // (a coral Joana next to brick-red Hugheses reads as blood). Hue distance
  // is measured in OKLCH, not HSL: HSL called grass-green "far" from teal
  // (80°) and painted Dustin as a Tuna — perceptually both are just green.
  const hueOf = (hex) => {
    const n = parseInt(hex.slice(1), 16);
    const lin = (c) => {
      const x = c / 255;
      return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    };
    const r = lin((n >> 16) & 255);
    const g = lin((n >> 8) & 255);
    const b = lin(n & 255);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
    const b2 = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
    return ((Math.atan2(b2, a) * 180) / Math.PI + 360) % 360;
  };
  const PALETTE_HUES = SUBLINE_COLORS.map(hueOf);
  const hueDist = (a, b) => {
    const x = Math.abs(a - b) % 360;
    return x > 180 ? 360 - x : x;
  };
  // A minor line must clear every MAJOR line's hue by a wide margin — that
  // is the confusion that matters (a married-in resembling the blood family
  // they render beside). Spacing minors from each other is only secondary:
  // with many married-ins the wheel fills up, and "farthest from everything"
  // degenerated into picking greens beside the teal Tuna line.
  const MAJOR_CLEARANCE = 60;
  const pickMinorColor = () => {
    const majorHues = sublines.filter((s) => !s.minor).map((s) => hueOf(s.color));
    const usedColors = new Set(sublines.map((s) => s.color));
    const usedHues = sublines.map((s) => hueOf(s.color));
    let candidates = SUBLINE_COLORS.filter((c) => !usedColors.has(c));
    if (!candidates.length) candidates = SUBLINE_COLORS;
    const clearOfMajors = candidates.filter((c) => {
      const h = PALETTE_HUES[SUBLINE_COLORS.indexOf(c)];
      return majorHues.every((m) => hueDist(m, h) >= MAJOR_CLEARANCE);
    });
    const pool = clearOfMajors.length ? clearOfMajors : candidates;
    let best = pool[0];
    let bestScore = -1;
    for (const c of pool) {
      const h = PALETTE_HUES[SUBLINE_COLORS.indexOf(c)];
      // Distance from majors dominates; distance from other assigned colors
      // only spreads minors within the safe arc.
      const majorScore = majorHues.length ? Math.min(...majorHues.map((m) => hueDist(m, h))) : 360;
      const usedScore = usedHues.length ? Math.min(...usedHues.map((u) => hueDist(u, h))) : 360;
      const score = majorScore * 4 + usedScore;
      if (score > bestScore) {
        bestScore = score;
        best = c;
      }
    }
    return best;
  };

  const addSubline = (root, minor) => {
    const idx = sublines.length;
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

    for (const pid of members) (byPerson[pid] ||= []).push(idx);
    sublines.push({
      label,
      color: minor ? pickMinorColor() : SUBLINE_COLORS[idx % SUBLINE_COLORS.length],
      minor: !!minor,
    });
  };
  roots.forEach((root) => addSubline(root, false));

  // ── Minor sublines: married-in spouses found their own line ──
  // A spouse with no blood membership shouldn't stay colorless: they root a
  // personal subline (at their parents' couple when shown, so siblings who
  // married into the family share one line) and their children inherit it.
  // Only spouses of people already colored above found one, so color doesn't
  // creep outward marriage by marriage into distant in-law branches.
  const minorRoots = [];
  for (const p of S.DATA.people) {
    if (byPerson[p.id]) continue;
    if (!(partnersOf[p.id] || []).some((s) => byPerson[s])) continue;
    for (const root of rootsAbove(p.id, 1)) {
      const key = [...root.ids].sort().join("|");
      if (seenRoot.has(key)) continue;
      seenRoot.add(key);
      minorRoots.push(root);
    }
  }
  minorRoots.forEach((root) => addSubline(root, true));

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

