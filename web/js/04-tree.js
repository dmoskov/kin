// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";
import { _resolveCenterIds } from "./02-lanes.js";
import { applyVisibilityFilter } from "./03-data-nav.js";


function _computeAge(birthDateStr) {
  if (!birthDateStr) return null;
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?/.exec(String(birthDateStr));
  if (!m) return null;
  const by = parseInt(m[1], 10);
  const bm = m[2] ? parseInt(m[2], 10) : null;
  const bd = m[3] ? parseInt(m[3], 10) : null;
  const now = new Date();
  let age = now.getFullYear() - by;
  if (bm !== null) {
    const nowM = now.getMonth() + 1;
    if (nowM < bm || (nowM === bm && bd !== null && now.getDate() < bd)) age--;
  }
  return age >= 0 ? age : null;
}

// Layout constants
export const NODE_W = 160;
export const NODE_H = 52;
export const COUPLE_GAP = 18;
export const H_SPACING = 10;
export const ROW_HEIGHT = 95;
export const BAND_PADDING = 20;

// Generation band gradient — warm center → cool ancestors
export const GEN_COLORS = [
  { gen:  1, color: "#c4956a", label: "Children" },
  { gen:  0, color: "#d4a843", label: "Center" },
  { gen: -1, color: "#d48c6a", label: "Parents" },
  { gen: -2, color: "#c47c6a", label: "Grandparents" },
  { gen: -3, color: "#a07c8a", label: "Great-Grandparents" },
  { gen: -4, color: "#8a7ca0", label: "2\u00d7 Great" },
  { gen: -5, color: "#7c8ab0", label: "3\u00d7 Great" },
  { gen: -6, color: "#6a8fb5", label: "4\u00d7 Great" },
  { gen: -7, color: "#5a9eb0", label: "5\u00d7 Great" },
  { gen: -8, color: "#4aa0a0", label: "6\u00d7 Great" },
  { gen: -9, color: "#3aa090", label: "7\u00d7 Great" },
  { gen:-10, color: "#2e9a80", label: "8\u00d7 Great" },
];

export function getGenMeta(gen) {
  return GEN_COLORS.find((g) => g.gen === gen) || {
    gen,
    color: "#6a8fb5",
    label: `${Math.abs(gen) - 2}\u00d7 Great`,
  };
}

export function buildHierarchy() {
  // Build parent→children lookup
  const childrenOf = {};
  const hasParent = new Set();

  for (const rel of S.DATA.relationships) {
    if (!childrenOf[rel.parent_id]) childrenOf[rel.parent_id] = new Set();
    childrenOf[rel.parent_id].add(rel.child_id);
    hasParent.add(rel.child_id);
  }

  // Build union lookup (partner mapping)
  const unionPartner = {};
  for (const u of S.DATA.unions) {
    if (!unionPartner[u.partner1_id]) unionPartner[u.partner1_id] = [];
    unionPartner[u.partner1_id].push(u.partner2_id);
    if (!unionPartner[u.partner2_id]) unionPartner[u.partner2_id] = [];
    unionPartner[u.partner2_id].push(u.partner1_id);
  }

  // Find family units (couples with children)
  // Strategy: group by "couple node" — pick the male partner or first partner as primary
  const processed = new Set();
  const roots = [];

  function buildNode(personId, depth = 0) {
    if (processed.has(personId) || depth > 10) return null;
    processed.add(personId);

    const person = S.PEOPLE_MAP[personId];
    if (!person) return null;

    const node = {
      id: personId,
      name: person.fullName,
      gender: person.gender,
      birthDate: person.birth_date,
      deathDate: person.death_date,
      data: person,
      children: [],
      partner: null,
    };

    // Find partner(s)
    const partners = (unionPartner[personId] || []).filter(
      (pid) => !processed.has(pid)
    );
    if (partners.length > 0) {
      const partnerId = partners[0];
      processed.add(partnerId);
      const partnerPerson = S.PEOPLE_MAP[partnerId];
      if (partnerPerson) {
        node.partner = {
          id: partnerId,
          name: partnerPerson.fullName,
          gender: partnerPerson.gender,
          data: partnerPerson,
        };
      }
    }

    // Collect children from both partners
    const childIds = new Set();
    if (childrenOf[personId]) {
      childrenOf[personId].forEach((c) => childIds.add(c));
    }
    if (node.partner && childrenOf[node.partner.id]) {
      childrenOf[node.partner.id].forEach((c) => childIds.add(c));
    }

    for (const cid of childIds) {
      const childNode = buildNode(cid, depth + 1);
      if (childNode) node.children.push(childNode);
    }

    return node;
  }

  // Start from people who have no parents (roots)
  for (const p of S.DATA.people) {
    if (!hasParent.has(p.id) && !processed.has(p.id)) {
      // Check if this person has a partner who is also a root — merge them
      const partners = unionPartner[p.id] || [];
      const rootPartner = partners.find(
        (pid) => !hasParent.has(pid) && !processed.has(pid)
      );

      // Pick the first one (male preference for layout consistency)
      const startId =
        p.gender === "male"
          ? p.id
          : rootPartner && S.PEOPLE_MAP[rootPartner]?.gender === "male"
          ? rootPartner
          : p.id;

      const node = buildNode(startId);
      if (node) roots.push(node);
    }
  }

  // If we have multiple root trees, create a virtual root
  if (roots.length === 1) return roots[0];
  return { id: "_root", name: "", virtual: true, children: roots, gender: "unknown" };
}

/**
 * Compute "fog of war" distance from the center couple's bloodline outward.
 * Distance 0 = bloodline (center couple + blood ancestors/descendants),
 * 1 = their partners (married in) and blood aunts/uncles (children of
 * blood ancestors), 2+ = in-law branches and collateral descendants.
 *
 * Shared by the tree (visual dimming) and the map (proximity filtering). Pass
 * the data source: the tree uses S.DATA; the map uses S.ORIGINAL_DATA so focus-mode
 * filtering doesn't drop ancestors/relatives.
 */
export function computeFogDistance(src) {
  if (!src) return {};
  const parentsOf = {};
  const childrenOf = {};
  for (const r of src.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
    if (!childrenOf[r.parent_id]) childrenOf[r.parent_id] = new Set();
    childrenOf[r.parent_id].add(r.child_id);
  }
  const unionPartner = {};
  for (const u of src.unions) {
    unionPartner[u.partner1_id] = unionPartner[u.partner1_id] || [];
    unionPartner[u.partner1_id].push(u.partner2_id);
    unionPartner[u.partner2_id] = unionPartner[u.partner2_id] || [];
    unionPartner[u.partner2_id].push(u.partner1_id);
  }
  const bloodline = new Set();
  // Separate visited sets per direction: otherwise tracing descendants would
  // bail immediately because the center was already added while tracing
  // ancestors, leaving the center's own descendants out of the bloodline
  // (distance 0). Descendants are blood relatives and must be distance 0.
  const seenUp = new Set();
  const seenDown = new Set();
  function traceUp(pid) {
    if (seenUp.has(pid)) return;
    seenUp.add(pid);
    bloodline.add(pid);
    for (const par of parentsOf[pid] || []) traceUp(par);
  }
  function traceDown(pid) {
    if (seenDown.has(pid)) return;
    seenDown.add(pid);
    bloodline.add(pid);
    for (const kid of childrenOf[pid] || new Set()) traceDown(kid);
  }
  if (S.CENTER_ID_A) {
    traceUp(S.CENTER_ID_A);
    traceDown(S.CENTER_ID_A);
  }
  if (S.CENTER_ID_B) {
    traceUp(S.CENTER_ID_B);
    traceDown(S.CENTER_ID_B);
  }
  // The center couple's own siblings are immediate family (distance 0), not
  // distant in-laws. They're neither ancestors nor descendants, so without
  // this they'd be unreachable by the BFS below (which seeds from partners)
  // and fall through to max fog — hidden until the "Everyone" depth level.
  function addSiblings(pid) {
    if (!pid) return;
    for (const par of parentsOf[pid] || []) {
      for (const sib of childrenOf[par] || new Set()) bloodline.add(sib);
    }
  }
  addSiblings(S.CENTER_ID_A);
  addSiblings(S.CENTER_ID_B);
  const fog = {};
  for (const id of bloodline) fog[id] = 0;
  // Partners of bloodline = distance 1
  for (const u of src.unions) {
    if (bloodline.has(u.partner1_id) && !bloodline.has(u.partner2_id)) {
      if (fog[u.partner2_id] === undefined) fog[u.partner2_id] = 1;
    }
    if (bloodline.has(u.partner2_id) && !bloodline.has(u.partner1_id)) {
      if (fog[u.partner1_id] === undefined) fog[u.partner1_id] = 1;
    }
  }
  // BFS outward through parent/child/union edges, in distance order, seeded
  // from everything already assigned (bloodline = 0, married-in partners = 1).
  // Seeding from the bloodline too means children of blood ancestors — aunts/
  // uncles and their branches — inherit distance from their bloodline parent
  // (a great-uncle is 1, his wife and children 2) instead of being unreachable
  // and falling to max fog (hidden until the "Everyone" depth level).
  const buckets = [];
  for (const [id, d] of Object.entries(fog)) (buckets[d] ||= []).push(id);
  for (let dist = 0; dist < 10; dist++) {
    for (const pid of buckets[dist] || []) {
      const assign = (n) => {
        if (fog[n] === undefined) {
          fog[n] = dist + 1;
          (buckets[dist + 1] ||= []).push(n);
        }
      };
      for (const par of parentsOf[pid] || []) assign(par);
      for (const kid of childrenOf[pid] || new Set()) assign(kid);
      for (const partner of unionPartner[pid] || []) assign(partner);
    }
  }
  return fog;
}

/**
 * Build the butterfly layout data structure.
 * Returns { nodes, links, unions, genRange }
 */
export function buildButterflyLayout() {
  _resolveCenterIds();

  const parentsOf = {};
  const childrenOf = {};
  for (const r of S.DATA.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
    if (!childrenOf[r.parent_id]) childrenOf[r.parent_id] = new Set();
    childrenOf[r.parent_id].add(r.child_id);
  }

  const unionPartner = {};
  for (const u of S.DATA.unions) {
    unionPartner[u.partner1_id] = unionPartner[u.partner1_id] || [];
    unionPartner[u.partner1_id].push(u.partner2_id);
    unionPartner[u.partner2_id] = unionPartner[u.partner2_id] || [];
    unionPartner[u.partner2_id].push(u.partner1_id);
  }

  const couples = [];
  const personCoupleIdx = {};
  const placed = new Set();

  function addCouple(primaryId, partnerId, gen, side, treePar) {
    const idx = couples.length;
    couples.push({ primaryId, partnerId, gen, side, treeParent: treePar ?? -1 });
    placed.add(primaryId);
    personCoupleIdx[primaryId] = idx;
    if (partnerId) {
      placed.add(partnerId);
      personCoupleIdx[partnerId] = idx;
    }
    return idx;
  }

  // Gen 0: center couple
  const centerIdx = addCouple(S.CENTER_ID_A, S.CENTER_ID_B, 0, "center", -1);

  // Gen +1: children of center couple
  const centerChildren = new Set();
  (childrenOf[S.CENTER_ID_A] || new Set()).forEach((c) => centerChildren.add(c));
  (childrenOf[S.CENTER_ID_B] || new Set()).forEach((c) => centerChildren.add(c));
  for (const cid of centerChildren) {
    if (!placed.has(cid)) {
      const partner = (unionPartner[cid] || []).find((p) => !placed.has(p)) || null;
      addCouple(cid, partner, 1, "center", centerIdx);
    }
  }

  // Gen 0: the center couple's siblings — rendered prominently beside the
  // center couple instead of being buried under the parents' subtree. We do
  // BOTH partners: partner A's siblings AND partner B's (the siblings-in-law).
  // order < 0 sits left of center, order > 0 sits right, so each partner's
  // siblings cluster on that partner's side.
  function addCenterSiblings(centerPersonId, orderSign) {
    if (!centerPersonId) return;
    const sibs = new Set();
    for (const par of parentsOf[centerPersonId] || []) {
      for (const kid of childrenOf[par] || new Set()) {
        if (kid !== centerPersonId) sibs.add(kid);
      }
    }
    for (const sid of sibs) {
      if (placed.has(sid)) continue;
      const partner = (unionPartner[sid] || []).find((p) => !placed.has(p)) || null;
      const idx = addCouple(sid, partner, 0, "center");
      couples[idx].order = orderSign;
    }
  }
  addCenterSiblings(S.CENTER_ID_A, -2);
  addCenterSiblings(S.CENTER_ID_B, 2);

  // Walk UP from a person to place their ancestors.
  // Ancestors are stored as tree-children of their descendant (butterfly/inverted direction).
  // This keeps the center couple as the tree root with both parent lines as subtrees.
  // Group a person's not-yet-placed parents into {primaryId, partnerId} couples.
  // Shared by walkAncestors and walkAncestorsSplit.
  function buildParentPairs(personId) {
    const parents = (parentsOf[personId] || []).filter((p) => !placed.has(p));
    const usedParents = new Set();
    const parentPairs = [];
    for (const pid of parents) {
      if (usedParents.has(pid)) continue;
      const partners = (unionPartner[pid] || []).filter(
        (p) => parents.includes(p) && !usedParents.has(p) && p !== pid
      );
      const partnerId = partners[0] || null;
      usedParents.add(pid);
      if (partnerId) usedParents.add(partnerId);
      parentPairs.push({ primaryId: pid, partnerId });
    }
    return parentPairs;
  }

  function walkAncestors(personId, gen, side, childCoupleIdx) {
    const parentPairs = buildParentPairs(personId);
    if (parentPairs.length === 0) return;

    for (const pair of parentPairs) {
      const idx = addCouple(pair.primaryId, pair.partnerId, gen - 1, side, childCoupleIdx);
      walkAncestors(pair.primaryId, gen - 1, side, idx);
      if (pair.partnerId) walkAncestors(pair.partnerId, gen - 1, side, idx);
    }
  }

  // Split S.CENTER_ID_A's parents into left/right sides for balanced layout.
  // Without this, ALL of one partner's ancestry goes to one side, creating
  // a lopsided tree when that partner has deep ancestry on both parent lines.
  function walkAncestorsSplit(personId, gen, childCoupleIdx) {
    const parentPairs = buildParentPairs(personId);
    if (parentPairs.length === 0) return;

    if (parentPairs.length === 1 && parentPairs[0].partnerId) {
      // Single parent couple: split the two parents into right/left sides
      const pair = parentPairs[0];
      const idx = addCouple(pair.primaryId, pair.partnerId, gen - 1, "right", childCoupleIdx);
      // Primary parent's ancestors → right side (positioned left)
      walkAncestors(pair.primaryId, gen - 1, "right", idx);
      // Partner parent's ancestors → left side (positioned right)
      walkAncestors(pair.partnerId, gen - 1, "left", idx);
    } else {
      // Multiple parent pairs or single parent: alternate sides
      for (let pi = 0; pi < parentPairs.length; pi++) {
        const pair = parentPairs[pi];
        const side = pi % 2 === 0 ? "right" : "left";
        const idx = addCouple(pair.primaryId, pair.partnerId, gen - 1, side, childCoupleIdx);
        walkAncestors(pair.primaryId, gen - 1, side, idx);
        if (pair.partnerId) walkAncestors(pair.partnerId, gen - 1, side, idx);
      }
    }
  }

  walkAncestorsSplit(S.CENTER_ID_A, 0, centerIdx);
  if (S.CENTER_ID_B) walkAncestorsSplit(S.CENTER_ID_B, 0, centerIdx);

  // Walk DOWN from every placed person to include siblings, aunts/uncles
  function walkDescendants(personId, gen, side, parentCoupleIdx) {
    const kids = childrenOf[personId] || new Set();
    for (const cid of kids) {
      if (placed.has(cid)) continue;
      const partner = (unionPartner[cid] || []).find((p) => !placed.has(p)) || null;
      const idx = addCouple(cid, partner, gen + 1, side, parentCoupleIdx);
      walkDescendants(cid, gen + 1, side, idx);
      if (partner) walkDescendants(partner, gen + 1, side, idx);
    }
  }

  const snapshotLen = couples.length;
  for (let i = 0; i < snapshotLen; i++) {
    const c = couples[i];
    walkDescendants(c.primaryId, c.gen, c.side, i);
    if (c.partnerId) walkDescendants(c.partnerId, c.gen, c.side, i);
  }

  // Catch remaining connected people (e.g. second spouses)
  for (const p of S.DATA.people) {
    if (placed.has(p.id)) continue;
    const partners = unionPartner[p.id] || [];
    const placedPartner = partners.find((pid) => placed.has(pid));
    if (placedPartner) {
      const pcIdx = personCoupleIdx[placedPartner];
      const partnerCouple = couples[pcIdx];
      if (partnerCouple) addCouple(p.id, null, partnerCouple.gen, partnerCouple.side, partnerCouple.treeParent);
    }
    const pars = parentsOf[p.id] || [];
    const placedParent = pars.find((pid) => placed.has(pid));
    if (!placed.has(p.id) && placedParent) {
      const ppIdx = personCoupleIdx[placedParent];
      const parentCouple = couples[ppIdx];
      if (parentCouple) addCouple(p.id, null, parentCouple.gen + 1, parentCouple.side, ppIdx);
    }
  }

  // ── Compute positions (compact layer-by-layer layout) ──
  //
  // Uses a Sugiyama-style barycenter algorithm instead of recursive subtree-
  // width allocation. Each generation is positioned independently:
  //   1. Place roots compactly
  //   2. Top-down: place each child at its parent's x, resolve overlaps
  //   3. Bottom-up: re-center each parent over its children, resolve overlaps
  //   4. Repeat for convergence
  //
  // This produces dramatically more compact layouts because ancestors are only
  // spread as far as needed to avoid overlaps — not pre-allocated for all
  // leaf-level descendants.

  const genRange = { min: 0, max: 0 };
  for (const c of couples) {
    genRange.min = Math.min(genRange.min, c.gen);
    genRange.max = Math.max(genRange.max, c.gen);
  }

  function coupleWidth(c) {
    return c.partnerId ? NODE_W * 2 + COUPLE_GAP : NODE_W;
  }

  function genY(gen) {
    return (gen - genRange.min) * ROW_HEIGHT + BAND_PADDING;
  }

  const couplePositions = new Map();

  // ── Build natural parent→child trees for ancestor lines ──

  function buildNaturalTree(lineIndices) {
    const inLine = new Set(lineIndices);
    const natKids = {};
    const hasParent = new Set();

    for (const idx of lineIndices) {
      const c = couples[idx];
      const bioKids = new Set();
      if (childrenOf[c.primaryId]) childrenOf[c.primaryId].forEach(k => bioKids.add(k));
      if (c.partnerId && childrenOf[c.partnerId]) childrenOf[c.partnerId].forEach(k => bioKids.add(k));

      for (const kidId of bioKids) {
        const kidIdx = personCoupleIdx[kidId];
        if (kidIdx !== undefined && inLine.has(kidIdx) && kidIdx !== idx) {
          if (!natKids[idx]) natKids[idx] = [];
          if (!natKids[idx].includes(kidIdx)) {
            natKids[idx].push(kidIdx);
            hasParent.add(kidIdx);
          }
        }
      }
    }

    const roots = lineIndices.filter(i => !hasParent.has(i));
    return { natKids, roots };
  }

  // ── Layer-by-layer positioning (barycenter method) ──
  // Works for any tree expressed as a childrenMap. Multiple top-down + bottom-up
  // passes converge to a compact, balanced layout.

  function positionLayered(allIndicesArr, childrenMap) {
    const allIndices = new Set(allIndicesArr);
    if (allIndices.size === 0) return;

    // Build parent map
    const parentOf = {};
    for (const idx of allIndices) {
      for (const kid of (childrenMap[idx] || [])) {
        if (allIndices.has(kid)) parentOf[kid] = idx;
      }
    }

    // Group by generation
    const byGen = {};
    for (const idx of allIndices) {
      const g = couples[idx].gen;
      if (!byGen[g]) byGen[g] = [];
      byGen[g].push(idx);
    }

    const gens = Object.keys(byGen).map(Number).sort((a, b) => a - b);
    if (gens.length === 0) return;

    // Resolve overlaps in a generation, then re-center the group so the
    // median stays stable (prevents rightward drift).
    function resolveOverlaps(group) {
      if (group.length <= 1) return;
      group.sort((a, b) => couplePositions.get(a).cx - couplePositions.get(b).cx);
      // Remember center of mass before
      const cmBefore = group.reduce((s, i) => s + couplePositions.get(i).cx, 0) / group.length;
      // Push apart
      for (let i = 1; i < group.length; i++) {
        const prev = couplePositions.get(group[i - 1]);
        const curr = couplePositions.get(group[i]);
        const minGap = (coupleWidth(couples[group[i - 1]]) + coupleWidth(couples[group[i]])) / 2 + H_SPACING;
        if (curr.cx - prev.cx < minGap) {
          curr.cx = prev.cx + minGap;
        }
      }
      // Re-center group around original center of mass
      const cmAfter = group.reduce((s, i) => s + couplePositions.get(i).cx, 0) / group.length;
      const drift = cmAfter - cmBefore;
      for (const idx of group) couplePositions.get(idx).cx -= drift;
    }

    // Initial placement: roots packed compactly, centered at x=0.
    // Honor an explicit `order` hint (used to flank the center couple with
    // partner A's siblings on the left and partner B's on the right).
    const rootGroup = byGen[gens[0]];
    rootGroup.sort((a, b) => (couples[a].order || 0) - (couples[b].order || 0));
    let rx = 0;
    for (const idx of rootGroup) {
      const w = coupleWidth(couples[idx]);
      couplePositions.set(idx, { cx: rx + w / 2, y: genY(couples[idx].gen) });
      rx += w + H_SPACING;
    }
    if (rootGroup.length > 0) {
      const avg = rootGroup.reduce((s, i) => s + couplePositions.get(i).cx, 0) / rootGroup.length;
      for (const idx of rootGroup) couplePositions.get(idx).cx -= avg;
    }

    // Run 3 iterations of top-down + bottom-up for convergence
    for (let iter = 0; iter < 3; iter++) {
      // Top-down: each child at parent's x
      for (let gi = 1; gi < gens.length; gi++) {
        const group = byGen[gens[gi]];
        for (const idx of group) {
          const par = parentOf[idx];
          const parPos = par !== undefined ? couplePositions.get(par) : null;
          const cx = parPos ? parPos.cx : 0;
          if (couplePositions.has(idx)) {
            couplePositions.get(idx).cx = cx;
          } else {
            couplePositions.set(idx, { cx, y: genY(couples[idx].gen) });
          }
        }
        resolveOverlaps(group);
      }

      // Bottom-up: each parent at average of children
      for (let gi = gens.length - 1; gi >= 0; gi--) {
        const group = byGen[gens[gi]];
        for (const idx of group) {
          const kids = (childrenMap[idx] || []).filter(k => allIndices.has(k) && couplePositions.has(k));
          if (kids.length === 0) continue;
          couplePositions.get(idx).cx = kids.reduce((s, k) => s + couplePositions.get(k).cx, 0) / kids.length;
        }
        resolveOverlaps(group);
      }
    }
  }

  // Helper: collect all indices reachable from roots
  function collectAll(roots, childrenMap) {
    const all = [];
    const visited = new Set();
    function walk(idx) {
      if (visited.has(idx)) return;
      visited.add(idx);
      all.push(idx);
      for (const kid of (childrenMap[idx] || [])) walk(kid);
    }
    for (const r of roots) walk(r);
    return all;
  }

  // Helper: shift all positioned indices by dx
  function shiftAll(indices, dx) {
    for (const idx of indices) {
      const pos = couplePositions.get(idx);
      if (pos) pos.cx += dx;
    }
  }

  // Helper: get horizontal extent
  function getExtent(indices) {
    let min = Infinity, max = -Infinity;
    for (const idx of indices) {
      const pos = couplePositions.get(idx);
      if (pos) {
        const hw = coupleWidth(couples[idx]) / 2;
        min = Math.min(min, pos.cx - hw);
        max = Math.max(max, pos.cx + hw);
      }
    }
    return { min, max };
  }

  // ── Group couples by side ──
  const rightLine = []; // partner A's family (side="right") → positioned LEFT
  const leftLine = [];  // partner B's family (side="left")  → positioned RIGHT
  for (let i = 0; i < couples.length; i++) {
    if (i === centerIdx) continue;
    if (couples[i].side === "right") rightLine.push(i);
    else if (couples[i].side === "left") leftLine.push(i);
  }

  // ── Position the center "family of origin" block at x=0 ──
  // This block holds the center couple, BOTH partners' siblings (rendered at
  // gen 0 flanking the couple), and all of their descendants. Siblings are
  // first-class here instead of being buried under the parents' subtree.
  const centerLine = [];
  for (let i = 0; i < couples.length; i++) {
    if (couples[i].side === "center") centerLine.push(i);
  }
  const centerTree = buildNaturalTree(centerLine);
  const descAll = collectAll(centerTree.roots, centerTree.natKids);
  positionLayered(descAll, centerTree.natKids);

  // Align an ancestor line so the center person's parents sit centered over
  // their children (the center person + that person's siblings), rather than
  // shoved entirely off to one side.
  function alignLineOverChildren(lineIndices, centerPersonId, onThisSide) {
    if (lineIndices.length === 0 || !centerPersonId) return;
    let anchorIdx;
    for (const pid of parentsOf[centerPersonId] || []) {
      if (personCoupleIdx[pid] !== undefined) { anchorIdx = personCoupleIdx[pid]; break; }
    }
    if (anchorIdx === undefined || !couplePositions.has(anchorIdx)) return;
    const group = [centerIdx];
    for (let i = 0; i < couples.length; i++) {
      if (couples[i].side === "center" && onThisSide(couples[i])) group.push(i);
    }
    let sum = 0, n = 0;
    for (const g of group) {
      const p = couplePositions.get(g);
      if (p) { sum += p.cx; n++; }
    }
    if (n === 0) return;
    shiftAll(lineIndices, sum / n - couplePositions.get(anchorIdx).cx);
  }

  // ── Position partner A's ancestry (LEFT) centered over A + A's siblings ──
  let allR = [];
  if (rightLine.length > 0) {
    const { natKids, roots } = buildNaturalTree(rightLine);
    allR = collectAll(roots, natKids);
    positionLayered(allR, natKids);
    alignLineOverChildren(allR, S.CENTER_ID_A, (c) => (c.order || 0) < 0);
  }

  // ── Position partner B's ancestry (RIGHT) centered over B + B's siblings ──
  let allL = [];
  if (leftLine.length > 0) {
    const { natKids, roots } = buildNaturalTree(leftLine);
    allL = collectAll(roots, natKids);
    positionLayered(allL, natKids);
    alignLineOverChildren(allL, S.CENTER_ID_B, (c) => (c.order || 0) > 0);
  }

  // Keep the two ancestor blocks from colliding after alignment.
  if (allR.length > 0 && allL.length > 0) {
    const rExt = getExtent(allR);
    const lExt = getExtent(allL);
    const overlap = rExt.max + H_SPACING * 2 - lExt.min;
    if (overlap > 0) {
      shiftAll(allR, -overlap / 2);
      shiftAll(allL, overlap / 2);
    }
  }

  // ── Position any orphan couples not yet positioned ──
  let maxX = 0;
  for (const [, pos] of couplePositions) {
    if (pos.cx + NODE_W > maxX) maxX = pos.cx + NODE_W;
  }
  for (let i = 0; i < couples.length; i++) {
    if (couplePositions.has(i)) continue;
    maxX += H_SPACING * 2;
    const w = coupleWidth(couples[i]);
    couplePositions.set(i, { cx: maxX + w / 2, y: genY(couples[i].gen) });
    maxX += w;
  }

  // Build flat node list
  const nodes = [];
  const nodeMap = {};
  for (let i = 0; i < couples.length; i++) {
    const c = couples[i];
    const pos = couplePositions.get(i);
    if (!pos) continue;

    const w = coupleWidth(c);
    const person = S.PEOPLE_MAP[c.primaryId];
    if (!person) continue;

    const primaryX = c.partnerId ? pos.cx - w / 2 : pos.cx - NODE_W / 2;
    const primaryNode = {
      id: c.primaryId, x: primaryX, y: pos.y, cx: primaryX + NODE_W / 2,
      gen: c.gen, side: c.side, person, coupleIdx: i,
    };
    nodes.push(primaryNode);
    nodeMap[c.primaryId] = primaryNode;

    if (c.partnerId) {
      const partnerPerson = S.PEOPLE_MAP[c.partnerId];
      if (partnerPerson) {
        const partnerX = primaryX + NODE_W + COUPLE_GAP;
        const partnerNode = {
          id: c.partnerId, x: partnerX, y: pos.y, cx: partnerX + NODE_W / 2,
          gen: c.gen, side: c.side, person: partnerPerson, coupleIdx: i,
        };
        nodes.push(partnerNode);
        nodeMap[c.partnerId] = partnerNode;
      }
    }
  }

  // Build links (child → parent)
  const links = [];
  for (const r of S.DATA.relationships) {
    const childNode = nodeMap[r.child_id];
    const parentNode = nodeMap[r.parent_id];
    if (childNode && parentNode) links.push({ from: childNode, to: parentNode });
  }

  // Build union connectors
  const unions = [];
  for (let i = 0; i < couples.length; i++) {
    const c = couples[i];
    if (!c.partnerId) continue;
    const n1 = nodeMap[c.primaryId];
    const n2 = nodeMap[c.partnerId];
    if (n1 && n2) {
      unions.push({
        x1: n1.x + NODE_W, y1: n1.y + NODE_H / 2,
        x2: n2.x, y2: n2.y + NODE_H / 2,
        id1: c.primaryId, id2: c.partnerId,
      });
    }
  }

  // ── Compute bloodline distance (fog-of-war) ──
  // Distance 0 = center couple + blood ancestors/descendants; 1 = their
  // partners; 2+ = in-law branches. Shared with the map via computeFogDistance.
  const fogDistance = computeFogDistance(S.DATA);

  // Assign fogLevel to each node: 0 = clear, 1-4 = increasing fog
  for (const n of nodes) {
    const dist = fogDistance[n.id] ?? 99;
    n.fogLevel = Math.min(dist, 4);
  }

  // Export fog distance globally so the map can filter by viewer proximity
  window._fogDistance = fogDistance;

  return { nodes, links, unions, genRange, couples, couplePositions };
}

// ── Tree pan/zoom controls (state populated by renderTree) ──────────────
let _treeZoom = null;
let _treeSvg = null;
let _treeDims = { width: 0, height: 0 };
let _treeBounds = { minX: 0, maxX: 0, minY: 0, maxY: 0 };
let _treeNodeById = {};

function _treeNodeCenter(n) {
  return { cx: n.cx != null ? n.cx : n.x + NODE_W / 2, cy: n.y + NODE_H / 2 };
}

export function zoomTreeBy(factor) {
  if (!_treeZoom || !_treeSvg) return;
  _treeSvg.transition().duration(200).call(_treeZoom.scaleBy, factor);
}

export function fitTreeToScreen() {
  if (!_treeZoom || !_treeSvg) return;
  const pad = 80;
  const cw = _treeBounds.maxX - _treeBounds.minX + pad * 2;
  const ch = _treeBounds.maxY - _treeBounds.minY + pad * 2;
  if (cw <= 0 || ch <= 0) return;
  const k = Math.min(_treeDims.width / cw, _treeDims.height / ch, 0.85);
  const tx = _treeDims.width / 2 - ((_treeBounds.minX + _treeBounds.maxX) / 2) * k;
  // Match the initial-load framing: top-anchor a width-filling tree so the
  // oldest generation sits near the top rather than floating mid-canvas;
  // center small/narrow trees.
  const topMargin = 32;
  const scaledWidth = (_treeBounds.maxX - _treeBounds.minX) * k;
  const scaledHeight = (_treeBounds.maxY - _treeBounds.minY) * k;
  const topAlign = scaledWidth >= _treeDims.width * 0.9 && scaledHeight + topMargin * 2 < _treeDims.height;
  const ty = topAlign
    ? topMargin - _treeBounds.minY * k
    : _treeDims.height / 2 - ((_treeBounds.minY + _treeBounds.maxY) / 2) * k;
  _treeSvg.transition().duration(450).call(_treeZoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
}

// Smoothly center the tree on a person, accounting for the person panel
// covering the right edge when it's open.
export function centerTreeOnNode(personId, opts = {}) {
  if (!_treeZoom || !_treeSvg) return;
  const n = _treeNodeById[personId];
  if (!n) return;
  const panel = document.getElementById("person-panel");
  const panelOpen = panel && !panel.classList.contains("hidden");
  const panelW = panelOpen ? panel.getBoundingClientRect().width || 0 : 0;
  const t = d3.zoomTransform(_treeSvg.node());
  const k = opts.scale || (t.k >= 0.5 ? t.k : 0.9);
  const { cx, cy } = _treeNodeCenter(n);
  const visibleW = Math.max(_treeDims.width - panelW, 200);
  const tx = visibleW / 2 - cx * k;
  const ty = _treeDims.height / 2 - cy * k;
  _treeSvg.transition().duration(450).call(_treeZoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
}

export function centerTreeOnMe() {
  centerTreeOnNode(S.CENTER_ID_A || S.CENTER_ID_B, { scale: 0.9 });
}

// Pan to a node only if it's currently off-screen or hidden behind the panel.
export function ensureTreeNodeVisible(personId) {
  if (!_treeZoom || !_treeSvg) return;
  const n = _treeNodeById[personId];
  if (!n) return;
  const t = d3.zoomTransform(_treeSvg.node());
  const { cx, cy } = _treeNodeCenter(n);
  const sx = cx * t.k + t.x;
  const sy = cy * t.k + t.y;
  const panel = document.getElementById("person-panel");
  const panelOpen = panel && !panel.classList.contains("hidden");
  const panelW = panelOpen ? panel.getBoundingClientRect().width || 0 : 0;
  const margin = 80;
  const onScreen =
    sx > margin &&
    sx < _treeDims.width - panelW - margin &&
    sy > margin &&
    sy < _treeDims.height - margin;
  if (!onScreen) centerTreeOnNode(personId);
}

// Highlight a chain of people (e.g. a relationship path) on the tree: dim
// everyone else and outline the path nodes. Uses inline styles so it clears on
// the next renderTree(). Pans to the first path node.
export function highlightTreePath(ids) {
  if (!_treeSvg || !ids || ids.length === 0) return;
  const set = new Set(ids);
  d3.selectAll(".node-group").style("opacity", (d) => (set.has(d.id) ? 1 : 0.18));
  d3.selectAll(".node-group")
    .select("rect")
    .style("stroke", (d) => (set.has(d.id) ? "var(--accent)" : null))
    .style("stroke-width", (d) => (set.has(d.id) ? 3 : null));
  centerTreeOnNode(ids[0]);
}

export function clearTreePathHighlight() {
  if (!_treeSvg) return;
  d3.selectAll(".node-group").style("opacity", null);
  d3.selectAll(".node-group").select("rect").style("stroke", null).style("stroke-width", null);
}

export function renderTree() {
  const svg = d3.select("#tree-svg");
  svg.selectAll("*").remove();

  const container = document.querySelector(".tree-container");
  const width = container.clientWidth;
  const height = container.clientHeight;
  svg.attr("width", width).attr("height", height)
     .attr("aria-label", "Family tree visualization — press Tab to navigate between people, Enter or Space to open a person's details")
     .attr("role", "group");

  const layout = buildButterflyLayout();
  if (!layout || layout.nodes.length === 0) return;

  // Apply tree depth filter — hide people beyond the selected complexity level.
  // depth 1 = bloodline + partners (fog 0-1), 2 = + in-law parents (fog 0-2),
  // 4 = everyone. Value 4 means "show all" (no filtering).
  const treeDepth = S.TREE_DEPTH;
  const maxFog = treeDepth >= 4 ? Infinity : treeDepth;
  const visibleIds = new Set(
    layout.nodes.filter(n => (n.fogLevel || 0) <= maxFog).map(n => n.id)
  );
  const nodes = layout.nodes.filter(n => visibleIds.has(n.id));
  const links = layout.links.filter(l => visibleIds.has(l.from.id) && visibleIds.has(l.to.id));
  const unions = layout.unions.filter(u => visibleIds.has(u.id1) && visibleIds.has(u.id2));
  const { genRange } = layout;

  // Calculate bounds
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const n of nodes) {
    minX = Math.min(minX, n.x);
    maxX = Math.max(maxX, n.x + NODE_W);
    minY = Math.min(minY, n.y);
    maxY = Math.max(maxY, n.y + NODE_H);
  }

  const padding = 80;

  // Zoom behavior
  const g = svg.append("g");
  // Photo-count badges are only shown when zoomed in past this threshold,
  // toggled as a pure CSS class on the SVG (no re-render).
  const BADGE_ZOOM_THRESHOLD = 0.5;
  const zoom = d3.zoom().scaleExtent([0.15, 2.5]).on("zoom", (e) => {
    g.attr("transform", e.transform);
    svg.classed("tree-zoomed-in", e.transform.k >= BADGE_ZOOM_THRESHOLD);
  });
  svg.call(zoom);

  // Frame the whole visible tree on load (fit-to-view), clamped so a tiny
  // family doesn't balloon and a sprawling one stays readable. Falls back to
  // centering on the focal couple when the tree is too big to fit usefully.
  const contentWidth = maxX - minX + padding * 2;
  const contentHeight = maxY - minY + padding * 2;
  const rawFit = Math.min(width / contentWidth, height / contentHeight);
  const fitScale = Math.max(0.2, Math.min(rawFit, 1.0));
  const centerNodeA = nodes.find(n => n.id === S.CENTER_ID_A);
  const centerNodeB = nodes.find(n => n.id === S.CENTER_ID_B);

  if (rawFit < 0.45 && centerNodeA) {
    // Tree won't fit at a readable scale — center on the focal couple instead.
    const focusX = centerNodeB ? (centerNodeA.cx + centerNodeB.cx) / 2 : centerNodeA.cx;
    const focusY = centerNodeA.y + NODE_H / 2;
    const k = 0.7;
    // Place the focal couple in the upper third rather than dead-centre: on a
    // narrow viewport the couple's ancestors fan out horizontally off-screen,
    // so centring vertically just opens an empty band above. Biasing upward
    // gives descendants the room and shrinks that band. The clamp still pulls
    // the tree up if the couple itself is near the top (few ancestors above),
    // so we never leave more than a small margin of dead space.
    const topMargin = 32;
    const tx = width / 2 - focusX * k;
    let ty = Math.min(height * 0.35 - focusY * k, topMargin - minY * k);
    // The upper-third bias still assumes some ancestor is visible above the
    // couple. On phone-width viewports they're often ALL off-screen to the
    // sides, leaving the band above the couple completely empty — detect
    // that and pull the couple near the top to reclaim it.
    const anyVisibleAbove = nodes.some((n) => {
      const ncx = n.cx != null ? n.cx : n.x + NODE_W / 2;
      const ncy = n.y + NODE_H / 2;
      if (ncy >= focusY - NODE_H) return false;
      const sx = ncx * k + tx;
      const sy = ncy * k + ty;
      return sy > 0 && sx > -NODE_W && sx < width + NODE_W;
    });
    if (!anyVisibleAbove) ty = height * 0.18 - focusY * k;
    svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  } else {
    const ftx = width / 2 - ((minX + maxX) / 2) * fitScale;
    // A wide tree fit-to-width leaves vertical slack. Centering it floats the
    // whole tree in dead space above the oldest generation; instead anchor the
    // top (oldest gen) near the viewport top and let the slack fall below,
    // where you'd scroll for descendants anyway. Only do this for trees that
    // actually fill the width — a small/narrow tree still reads best centered.
    const topMargin = 32;
    const scaledWidth = (maxX - minX) * fitScale;
    const scaledHeight = (maxY - minY) * fitScale;
    const topAlign = scaledWidth >= width * 0.9 && scaledHeight + topMargin * 2 < height;
    const fty = topAlign
      ? topMargin - minY * fitScale
      : height / 2 - ((minY + maxY) / 2) * fitScale;
    svg.call(zoom.transform, d3.zoomIdentity.translate(ftx, fty).scale(fitScale));
  }

  // Set the initial badge-visibility class to match the starting zoom level.
  svg.classed("tree-zoomed-in", d3.zoomTransform(svg.node()).k >= BADGE_ZOOM_THRESHOLD);

  // Expose for external pan/zoom controls (buttons, keyboard, panel centering).
  _treeZoom = zoom;
  _treeSvg = svg;
  _treeDims = { width, height };
  _treeBounds = { minX, maxX, minY, maxY };
  _treeNodeById = {};
  for (const n of nodes) _treeNodeById[n.id] = n;

  // ── 1. Generation bands ──
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  const bandExtent = maxX - minX + 600;

  for (let gen = genRange.min; gen <= genRange.max; gen++) {
    const meta = getGenMeta(gen);
    const bandY = (gen - genRange.min) * ROW_HEIGHT;
    const opacity = isLight ? 0.08 : 0.06;

    g.append("rect")
      .attr("class", "gen-band")
      .attr("x", minX - 300)
      .attr("y", bandY - 8)
      .attr("width", bandExtent)
      .attr("height", ROW_HEIGHT)
      .attr("fill", meta.color)
      .attr("opacity", opacity)
      .attr("rx", 6);

    g.append("text")
      .attr("class", "gen-label")
      .attr("x", minX - 20)
      .attr("y", bandY + ROW_HEIGHT / 2 + 2)
      .attr("text-anchor", "end")
      .attr("fill", meta.color)
      .attr("opacity", isLight ? 0.5 : 0.4)
      .attr("font-size", "11px")
      .attr("font-weight", "600")
      .attr("font-family", "'Inter', sans-serif")
      .text(meta.label);
  }

  // ── 2. Links (child → parent) — bus-bar grouped by parent couple ──
  // Instead of individual bezier curves, draw a single vertical drop from
  // the parent couple, a horizontal "bus bar" spanning all children, and
  // short verticals down to each child.  Much cleaner with many siblings.

  // Group links by parent node's coupleIdx to draw bus bars
  const linksByParentCouple = {};
  for (const l of links) {
    const key = l.to.coupleIdx;
    if (!linksByParentCouple[key]) linksByParentCouple[key] = [];
    linksByParentCouple[key].push(l);
  }

  for (const [, groupLinks] of Object.entries(linksByParentCouple)) {
    if (groupLinks.length === 0) continue;
    const parent = groupLinks[0].to;
    const fog = Math.max(...groupLinks.map(l => Math.max(l.from.fogLevel || 0, l.to.fogLevel || 0)));
    const fogClass = "link fog-" + Math.min(fog, 4);

    // Parent drop point: center of couple, bottom of node
    const parentCouple = layout.couples[parent.coupleIdx];
    const parentPos = layout.couplePositions.get(parent.coupleIdx);
    const dropX = parentPos ? parentPos.cx : parent.cx;
    const dropY = parent.y + NODE_H;

    // Children x positions
    const childXs = groupLinks.map(l => l.from.cx);
    const childY = groupLinks[0].from.y;
    const busY = dropY + (childY - dropY) * 0.5; // bus bar at midpoint

    const linkPersonIds = new Set([parent.id, ...groupLinks.map(l => l.from.id)]);

    if (groupLinks.length === 1) {
      const cx = childXs[0];
      const d = `M${dropX},${dropY} L${dropX},${busY} L${cx},${busY} L${cx},${childY}`;
      g.append("path")
        .datum({ personIds: linkPersonIds })
        .attr("class", fogClass)
        .attr("d", d);
      g.append("path").attr("class", "link-hit-area").attr("d", d);
    } else {
      const minX = Math.min(...childXs);
      const maxX = Math.max(...childXs);

      const d1 = `M${dropX},${dropY} L${dropX},${busY}`;
      g.append("path").datum({ personIds: linkPersonIds }).attr("class", fogClass).attr("d", d1);
      g.append("path").attr("class", "link-hit-area").attr("d", d1);

      const d2 = `M${minX},${busY} L${maxX},${busY}`;
      g.append("path").datum({ personIds: linkPersonIds }).attr("class", fogClass).attr("d", d2);
      g.append("path").attr("class", "link-hit-area").attr("d", d2);

      for (const cx of childXs) {
        const d3 = `M${cx},${busY} L${cx},${childY}`;
        g.append("path").datum({ personIds: linkPersonIds }).attr("class", fogClass).attr("d", d3);
        g.append("path").attr("class", "link-hit-area").attr("d", d3);
      }
    }
  }

  // ── 3. Union connectors ──
  // Attach fog info using the person IDs carried on each union connector
  const _nodeMap = {};
  for (const n of nodes) _nodeMap[n.id] = n;
  const unionsWithFog = unions.map((u) => {
    const f1 = _nodeMap[u.id1]?.fogLevel ?? 0;
    const f2 = _nodeMap[u.id2]?.fogLevel ?? 0;
    return { ...u, fogLevel: Math.max(f1, f2) };
  });
  g.selectAll(".union-link")
    .data(unionsWithFog)
    .enter()
    .append("line")
    .attr("class", (d) => "union-link fog-" + Math.min(d.fogLevel, 4))
    .attr("x1", (d) => d.x1)
    .attr("y1", (d) => d.y1)
    .attr("x2", (d) => d.x2)
    .attr("y2", (d) => d.y2);
  g.selectAll(".union-link-hit-area")
    .data(unionsWithFog)
    .enter()
    .append("line")
    .attr("class", "union-link-hit-area")
    .attr("x1", (d) => d.x1)
    .attr("y1", (d) => d.y1)
    .attr("x2", (d) => d.x2)
    .attr("y2", (d) => d.y2);

  // ── 4. Node cards ──
  // Sort so center couple (gen 0) renders last → on top in SVG
  const sortedNodes = [...nodes].sort((a, b) => {
    const aCenter = (a.id === S.CENTER_ID_A || a.id === S.CENTER_ID_B) ? 1 : 0;
    const bCenter = (b.id === S.CENTER_ID_A || b.id === S.CENTER_ID_B) ? 1 : 0;
    return aCenter - bCenter;
  });
  const nodeGroups = g
    .selectAll(".node-group")
    .data(sortedNodes)
    .enter()
    .append("g")
    .attr("class", (d) => "node-group fog-" + Math.min(d.fogLevel || 0, 4))
    .attr("transform", (d) => `translate(${d.x},${d.y})`)
    .attr("tabindex", "0")
    .attr("role", "button")
    .attr("aria-label", (d) => d.person.fullName);

  // Center nodes are drawn VISUALLY larger via a local overhang only — the
  // NODE_W/NODE_H globals (link/union/bounds/minimap math) are never changed.
  const CENTER_OVERHANG_X = 12;
  const CENTER_OVERHANG_Y = 8;
  const _isCenterId = (d) => d.id === S.CENTER_ID_A || d.id === S.CENTER_ID_B;
  nodeGroups
    .append("rect")
    .attr("class", (d) => "node-rect" + (_isCenterId(d) ? " center-node" : ""))
    .attr("x", (d) => (_isCenterId(d) ? -CENTER_OVERHANG_X : 0))
    .attr("y", (d) => (_isCenterId(d) ? -CENTER_OVERHANG_Y : 0))
    .attr("width", (d) => NODE_W + (_isCenterId(d) ? CENTER_OVERHANG_X * 2 : 0))
    .attr("height", (d) => NODE_H + (_isCenterId(d) ? CENTER_OVERHANG_Y * 2 : 0))
    .attr("fill", (d) => d.person.gender === "female" ? "var(--node-female-bg)" : d.person.gender === "other" ? "var(--node-other-bg)" : "var(--node-male-bg)")
    .attr("stroke", (d) => d.person.gender === "female" ? "var(--female)" : d.person.gender === "other" ? "var(--other)" : "var(--male)");

  // Photo thumbnails (circular, clipped)
  const PHOTO_SIZE = 28;
  const PHOTO_PAD = 6;
  // Avatar prominence is tiered by generation: the focal couple largest, the
  // recent generations (grandparents → children, where we actually have
  // photos) mid-size, deep ancestors compact. Each size needs its own
  // clipPath (a 28px circle would wrongly crop a larger image).
  const RECENT_PHOTO_SIZE = 36;
  const CENTER_PHOTO_SIZE = 44;
  const hasPhoto = (d) => !!d.person._profilePhotoPath;
  const isCenter = (d) => d.id === S.CENTER_ID_A || d.id === S.CENTER_ID_B;
  const isRecent = (d) => !isCenter(d) && (d.gen ?? -99) >= -2;
  const photoSizeFor = (d) =>
    isCenter(d) ? CENTER_PHOTO_SIZE : isRecent(d) ? RECENT_PHOTO_SIZE : PHOTO_SIZE;

  // Circular clips in node coordinates, one per avatar size, centered where
  // the avatar is actually drawn (left-padded, vertically centered). The
  // cropped branch must hang its clip on a wrapping <g>: a clip-path on the
  // nested <svg> itself resolves inside its viewBox (crop coords), where a
  // node-coord circle may not intersect at all — which blanked or
  // sliver-clipped cropped avatars.
  const defs = g.append("defs");
  for (const [suffix, sz] of [
    ["sm", PHOTO_SIZE],
    ["md", RECENT_PHOTO_SIZE],
    ["lg", CENTER_PHOTO_SIZE],
  ]) {
    defs.append("clipPath")
      .attr("id", `photo-clip-${suffix}`)
      .append("circle")
      .attr("cx", PHOTO_PAD + sz / 2)
      .attr("cy", NODE_H / 2)
      .attr("r", sz / 2);
  }
  const clipIdFor = (d) =>
    isCenter(d) ? "photo-clip-lg" : isRecent(d) ? "photo-clip-md" : "photo-clip-sm";

  // For cropped photos, use a nested <svg> with viewBox; uncropped use standard behavior
  nodeGroups.filter(hasPhoto).each(function(d) {
    const g = d3.select(this);
    const crop = d.person._profileCrop;
    const sz = photoSizeFor(d);
    const clipId = clipIdFor(d);
    if (crop) {
      // Match croppedImg() (03-data-nav.js), which the panel/hovercard/map use:
      // the crop is a square window in fractions of the photo's NATURAL width,
      // with the photo scaled by width and anchored top-left. Do the same here
      // in SVG so the tree avatar frames the exact region the crop editor and
      // panel show. (The old code pre-squashed the photo into a 1000² square
      // with `slice`, which shifted tall/wide photos so the same crop landed on
      // a different spot — visible as a mismatch between tree and panel.)
      //
      // Coordinate space = fractions of natural width: x∈[0,1] is full width,
      // y∈[0,aspectRatio]. The <image> width=1 with a tall box + "meet" forces
      // width-based scaling top-left WITHOUT needing the natural aspect ratio
      // (meet picks the smaller scale, which is always width here). The nested
      // <svg> windows to the square crop and clips the overflow.
      g.append("g")
        .attr("clip-path", `url(#${clipId})`)
        .append("svg")
        .attr("x", PHOTO_PAD)
        .attr("y", (NODE_H - sz) / 2)
        .attr("width", sz)
        .attr("height", sz)
        .attr("viewBox", `${crop.x} ${crop.y} ${crop.w} ${crop.w}`)
        .append("image")
        .attr("class", "node-photo")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", 1)
        .attr("height", 100) // > any real aspect ratio; "meet" clamps to width
        .attr("href", "/" + d.person._profilePhotoPath)
        .attr("preserveAspectRatio", "xMinYMin meet");
    } else {
      g.append("image")
        .attr("class", "node-photo")
        .attr("x", PHOTO_PAD)
        .attr("y", (NODE_H - sz) / 2)
        .attr("width", sz)
        .attr("height", sz)
        .attr("clip-path", `url(#${clipId})`)
        .attr("href", "/" + d.person._profilePhotoPath)
        .attr("preserveAspectRatio", "xMidYMid slice");
    }
    // A thin ring lifts the photo off the card and makes faces read as the
    // primary element of the node.
    g.append("circle")
      .attr("class", "node-photo-ring")
      .attr("cx", PHOTO_PAD + sz / 2)
      .attr("cy", NODE_H / 2)
      .attr("r", sz / 2 + 1)
      .attr("stroke", d.person.gender === "female" ? "var(--female)" : "var(--male)");
  });

  // Monogram fallback for people without a profile photo — a colored initial
  // disc, so EVERY node carries a "face" (matching the panel/list avatars).
  const monoGroups = nodeGroups.filter((d) => !hasPhoto(d));
  monoGroups
    .append("circle")
    .attr("class", "node-monogram")
    .attr("cx", (d) => PHOTO_PAD + photoSizeFor(d) / 2)
    .attr("cy", NODE_H / 2)
    .attr("r", (d) => photoSizeFor(d) / 2)
    .attr("fill", (d) => d.person.gender === "female" ? "var(--female)" : d.person.gender === "other" ? "var(--other)" : "var(--male)");
  monoGroups
    .append("text")
    .attr("class", "node-monogram-text")
    .attr("x", (d) => PHOTO_PAD + photoSizeFor(d) / 2)
    .attr("y", NODE_H / 2)
    .attr("text-anchor", "middle")
    .attr("dominant-baseline", "central")
    .style("font-size", (d) => (isCenter(d) ? "18px" : isRecent(d) ? "15px" : null))
    .text((d) => ((d.person.given_name || d.person.fullName || "?").trim()[0] || "?").toUpperCase());

  // Photo-count badge: a small accent disc at the avatar's bottom-right for
  // people with 2+ photos. Visibility is gated by zoom (CSS) to reduce clutter.
  const photoCount = (d) => _personPhotos(d.person.id).length;
  nodeGroups.filter((d) => photoCount(d) >= 2).each(function(d) {
    const grp = d3.select(this);
    const sz = photoSizeFor(d);
    const n = photoCount(d);
    const label = n > 9 ? "9+" : String(n);
    const cx = PHOTO_PAD + sz - 4;
    const cy = NODE_H / 2 + sz / 2 - 4;
    const badge = grp.append("g").attr("class", "node-photo-badge");
    badge.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 7);
    badge.append("text")
      .attr("x", cx)
      .attr("y", cy)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .text(label);
    badge.append("title").text(`${n} photos`);
  });
  // Append the photo count to the node's aria-label for screen readers.
  nodeGroups.filter((d) => photoCount(d) >= 2)
    .attr("aria-label", (d) => `${d.person.fullName}, ${photoCount(d)} photos`);

  // Every node now has an avatar, so text is always shifted right of it. The
  // center node's larger avatar pushes its text column further right.
  function textX(d) {
    const sz = photoSizeFor(d);
    return PHOTO_PAD + sz + 6 + (NODE_W - PHOTO_PAD - sz - 6) / 2;
  }
  function textAvailW(d) {
    const sz = photoSizeFor(d);
    return NODE_W - PHOTO_PAD - sz - 6 - 4;
  }

  // The larger recent-gen avatars leave less width for text. Long names drop
  // their middle names first (the given name is what distinguishes people
  // within a branch); pixel-measured ellipsis is the last resort. Full name
  // stays in the aria-label / panel.
  nodeGroups
    .append("text")
    .attr("class", (d) => "node-name" + (isCenter(d) || isRecent(d) ? " node-name-lg" : ""))
    .attr("x", textX)
    .attr("y", 20)
    .attr("text-anchor", "middle")
    .text((d) => d.person.fullName)
    .each(function (d) {
      const maxW = textAvailW(d);
      let txt = d.person.fullName || "";
      // Prefer dropping middle names (the given name is what distinguishes
      // people within a branch) before resorting to ellipsis.
      if (this.getComputedTextLength() > maxW) {
        const words = txt.split(/\s+/);
        if (words.length > 2) {
          txt = words[0] + " " + words[words.length - 1];
          d3.select(this).text(txt);
        }
      }
      while (this.getComputedTextLength() > maxW && txt.length > 1) {
        txt = txt.slice(0, -1);
        d3.select(this).text(txt + "…");
      }
    });

  nodeGroups
    .append("text")
    .attr("class", "node-dates")
    .attr("x", textX)
    .attr("y", 33)
    .attr("text-anchor", "middle")
    .text((d) => {
      const p = d.person;
      if (p.birth_date) {
        const y = dateYear(p.birth_date);
        if (!p.death_date) {
          const age = _computeAge(p.birth_date);
          // Young kids read best as a plain age; living adults in the recent
          // generations get year + age ("which cousin is this?").
          if (age !== null && age <= 17) return `Age ${age}`;
          if ((isRecent(d) || isCenter(d)) && age !== null && age < 110) {
            return `b. ${y} \u00b7 ${age}`;
          }
          return `b. ${y}`;
        }
        const dy = dateYear(p.death_date);
        return `${y} \u2013 ${dy || "?"}`;
      }
      return "";
    });

  // Third line: for recent generations prefer a "hook" \u2014 the person's latest
  // career/education event \u2014 which orients far better than the (often empty)
  // birth place. Ancestors keep birth place, which is how you navigate them.
  const eventsByPerson = {};
  for (const ev of S.DATA.events || []) {
    (eventsByPerson[ev.person_id] ||= []).push(ev);
  }
  const hookFor = (d) => {
    if (isRecent(d) || isCenter(d)) {
      const evs = eventsByPerson[d.person.id] || [];
      const latest = (type) =>
        evs
          .filter((e) => e.event_type === type && e.description)
          .sort((a, b) => (b.date || "").localeCompare(a.date || ""))[0];
      const ev = latest("career") || latest("education");
      if (ev) {
        // First clause only \u2014 descriptions are full sentences with sources.
        const clause = ev.description.split(/[;.]/)[0].trim();
        if (clause) return clause.length > 26 ? clause.substring(0, 25) + "\u2026" : clause;
      }
    }
    const place = d.person.birth_place;
    if (!place) return "";
    return place.length > 22 ? place.substring(0, 20) + "\u2026" : place;
  };
  nodeGroups
    .append("text")
    .attr("class", (d) => {
      const usedHook = (isRecent(d) || isCenter(d)) && (eventsByPerson[d.person.id] || [])
        .some((e) => (e.event_type === "career" || e.event_type === "education") && e.description);
      return usedHook ? "node-place node-hook" : "node-place";
    })
    .attr("x", textX)
    .attr("y", 44)
    .attr("text-anchor", "middle")
    .text(hookFor);

  nodeGroups.on("click", (e, d) => {
    e.stopPropagation();
    showPersonPanel(d.id);
    highlightNode(d.id);
    router.navigate(`/tree/person/${d.id}`);
    if (typeof _installPanelFocusTrap === "function") _installPanelFocusTrap();
  });

  nodeGroups.on("keydown", (e, d) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      showPersonPanel(d.id);
      highlightNode(d.id);
      router.navigate(`/tree/person/${d.id}`);
      if (typeof _installPanelFocusTrap === "function") _installPanelFocusTrap();
    }
  });

  // ── Fog-of-war hover reveal ──
  // Build adjacency for quick neighbor lookup
  const _fogAdj = {};
  const _addFogEdge = (a, b) => {
    (_fogAdj[a] || (_fogAdj[a] = new Set())).add(b);
    (_fogAdj[b] || (_fogAdj[b] = new Set())).add(a);
  };
  for (const r of S.DATA.relationships) { _addFogEdge(r.parent_id, r.child_id); }
  for (const u of S.DATA.unions) { _addFogEdge(u.partner1_id, u.partner2_id); }

  let _fogRevealTimer = null;

  function _fogNeighbors(personId, hops) {
    const visited = new Set([personId]);
    let front = [personId];
    for (let i = 0; i < hops; i++) {
      const next = [];
      for (const id of front) {
        for (const nb of (_fogAdj[id] || [])) {
          if (!visited.has(nb)) { visited.add(nb); next.push(nb); }
        }
      }
      front = next;
    }
    return visited;
  }

  function _fogReveal(reveal) {
    g.selectAll(".node-group").each(function(nd) {
      if (reveal.has(nd.id)) d3.select(this).classed("fog-revealed", true);
    });
    g.selectAll(".link").each(function(ld) {
      if (ld && ld.personIds) {
        for (const pid of ld.personIds) {
          if (reveal.has(pid)) { d3.select(this).classed("fog-revealed", true); break; }
        }
      }
    });
    g.selectAll(".union-link").each(function(ud) {
      const el = d3.select(this);
      if (el.classed("fog-1") || el.classed("fog-2") || el.classed("fog-3") || el.classed("fog-4")) {
        const ux = (+el.attr("x1") + +el.attr("x2")) / 2;
        const uy = (+el.attr("y1") + +el.attr("y2")) / 2;
        for (const rid of reveal) {
          const rn = nodes.find(n => n.id === rid);
          if (rn && Math.abs(rn.cx - ux) < NODE_W * 2 && Math.abs(rn.y + NODE_H/2 - uy) < NODE_H) {
            el.classed("fog-revealed", true);
            break;
          }
        }
      }
    });
  }

  function _fogHide() {
    clearTimeout(_fogRevealTimer);
    _fogRevealTimer = setTimeout(() => {
      g.selectAll(".fog-revealed").classed("fog-revealed", false);
    }, 600);
  }

  nodeGroups.on("mouseenter", (e, d) => {
    clearTimeout(_fogRevealTimer);
    if ((d.fogLevel || 0) === 0) return;
    _fogReveal(_fogNeighbors(d.id, 3));
  });

  nodeGroups.on("mouseleave", () => { _fogHide(); });

  g.selectAll(".link, .link-hit-area").on("mouseenter", () => { clearTimeout(_fogRevealTimer); });
  g.selectAll(".link, .link-hit-area").on("mouseleave", () => { _fogHide(); });
  g.selectAll(".union-link, .union-link-hit-area").on("mouseenter", () => { clearTimeout(_fogRevealTimer); });
  g.selectAll(".union-link, .union-link-hit-area").on("mouseleave", () => { _fogHide(); });

  // Background click to deselect and clear focus
  svg.on("click", () => {
    closePersonPanel();
    clearFocus();
    router.navigate("/tree");
  });

  // ── 6. Minimap (overview inset) ──
  const MINIMAP_W = 180, MINIMAP_H = 120;
  const mmPad = 10;
  const treeW = maxX - minX || 1;
  const treeH = maxY - minY || 1;
  const mmScale = Math.min((MINIMAP_W - mmPad * 2) / treeW, (MINIMAP_H - mmPad * 2) / treeH);

  // Remove old minimap if re-rendering
  d3.select("#tree-minimap").remove();

  const mmSvg = d3.select(".tree-container")
    .append("svg")
    .attr("id", "tree-minimap")
    .attr("width", MINIMAP_W)
    .attr("height", MINIMAP_H)
    .style("position", "absolute")
    .style("bottom", "12px")
    .style("right", "12px")
    .style("background", "var(--surface)")
    .style("border", "1px solid var(--border)")
    .style("border-radius", "var(--radius-sm)")
    .style("box-shadow", "var(--shadow-md)")
    .style("opacity", "0.96")
    .style("pointer-events", "all")
    .style("cursor", "pointer")
    .style("z-index", "10");

  const mmG = mmSvg.append("g")
    .attr("transform", `translate(${mmPad - minX * mmScale},${mmPad - minY * mmScale}) scale(${mmScale})`);

  // Draw node dots
  for (const n of nodes) {
    const fog = n.fogLevel || 0;
    mmG.append("rect")
      .attr("x", n.x)
      .attr("y", n.y)
      .attr("width", NODE_W)
      .attr("height", NODE_H)
      .attr("rx", 3)
      .attr("fill", n.person.gender === "female" ? "var(--female)" : n.person.gender === "other" ? "var(--other)" : "var(--male)")
      .attr("opacity", fog >= 3 ? 0.15 : fog >= 1 ? 0.4 : 0.7);
  }

  // Viewport indicator rectangle
  const mmViewport = mmSvg.append("rect")
    .attr("class", "minimap-viewport")
    .attr("fill", "rgba(var(--accent-rgb), 0.18)")
    .attr("stroke", "rgba(var(--accent-rgb), 0.9)")
    .attr("stroke-width", 1.5)
    .attr("rx", 3);

  function updateMinimapViewport(transform) {
    const vx = (-transform.x / transform.k);
    const vy = (-transform.y / transform.k);
    const vw = width / transform.k;
    const vh = height / transform.k;
    mmViewport
      .attr("x", mmPad + (vx - minX) * mmScale)
      .attr("y", mmPad + (vy - minY) * mmScale)
      .attr("width", vw * mmScale)
      .attr("height", vh * mmScale);
  }

  // Update minimap on zoom
  svg.call(zoom.on("zoom", (e) => {
    g.attr("transform", e.transform);
    svg.classed("tree-zoomed-in", e.transform.k >= BADGE_ZOOM_THRESHOLD);
    updateMinimapViewport(e.transform);
  }));

  // Initialize viewport indicator
  const currentTransform = d3.zoomTransform(svg.node());
  updateMinimapViewport(currentTransform);

  // Click minimap to pan
  mmSvg.on("click", (e) => {
    const [mx, my] = d3.pointer(e);
    const targetX = (mx - mmPad) / mmScale + minX;
    const targetY = (my - mmPad) / mmScale + minY;
    const t = d3.zoomTransform(svg.node());
    const newTx = width / 2 - targetX * t.k;
    const newTy = height / 2 - targetY * t.k;
    svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity.translate(newTx, newTy).scale(t.k));
  });
}

export function highlightNode(personId) {
  d3.selectAll(".node-group").classed("selected", (d) => d.id === personId);
}

// ═══════════════════════════════════════════════════════════════
// Focus Mode
// ═══════════════════════════════════════════════════════════════

// Walks S.DATA (the viewer-filtered base), not S.ORIGINAL_DATA, so the BFS
// can't reach people only connected through relationships hidden from the
// current viewer. applyFocus rebuilds S.DATA via applyVisibilityFilter()
// before calling this.
export function computeFocusSubgraph(personId, hops) {
  const adj = {};
  const addEdge = (a, b) => {
    (adj[a] || (adj[a] = [])).push(b);
    (adj[b] || (adj[b] = [])).push(a);
  };
  for (const r of S.DATA.relationships) addEdge(r.parent_id, r.child_id);
  for (const u of S.DATA.unions) addEdge(u.partner1_id, u.partner2_id);

  const visited = new Set([personId]);
  let frontier = [personId];
  for (let i = 0; i < hops; i++) {
    const next = [];
    for (const id of frontier) {
      for (const neighbor of (adj[id] || [])) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          next.push(neighbor);
        }
      }
    }
    frontier = next;
  }

  // Always include siblings (co-children of any parent) regardless of hop depth
  const parents = S.DATA.relationships
    .filter(r => r.child_id === personId)
    .map(r => r.parent_id);
  for (const parentId of parents) {
    for (const r of S.DATA.relationships) {
      if (r.parent_id === parentId && !visited.has(r.child_id)) {
        visited.add(r.child_id);
      }
    }
  }

  return visited;
}

export function applyFocus() {
  // Rebuild S.DATA from the viewer-filtered base — never raw S.ORIGINAL_DATA,
  // which would resurrect relationships hidden from the current viewer.
  applyVisibilityFilter();
  if (!S.FOCUS_PERSON_ID || S.FOCUS_DEPTH === "all") {
    // Restore the pre-focus center only if a snapshot exists. With no
    // snapshot (never focused, e.g. a background click), keep the current
    // center — nulling it would make _resolveCenterIds re-center the tree
    // on an arbitrary most-connected person.
    if (!S.FOCUS_PERSON_ID && S.ORIGINAL_CENTER_ID_A) {
      S.CENTER_ID_A = S.ORIGINAL_CENTER_ID_A;
      S.CENTER_ID_B = S.ORIGINAL_CENTER_ID_B;
    }
  } else {
    const base = S.DATA;
    const inScope = computeFocusSubgraph(S.FOCUS_PERSON_ID, S.FOCUS_DEPTH);
    S.DATA = {
      ...base,
      people: base.people.filter(p => inScope.has(p.id)),
      relationships: base.relationships.filter(r => inScope.has(r.parent_id) && inScope.has(r.child_id)),
      unions: base.unions.filter(u => inScope.has(u.partner1_id) && inScope.has(u.partner2_id)),
      events: (base.events || []).filter(e => inScope.has(e.person_id)),
    };
    S.CENTER_ID_A = S.FOCUS_PERSON_ID;
    const focusUnion = base.unions.find(
      u => u.partner1_id === S.FOCUS_PERSON_ID || u.partner2_id === S.FOCUS_PERSON_ID
    );
    S.CENTER_ID_B = focusUnion
      ? (focusUnion.partner1_id === S.FOCUS_PERSON_ID ? focusUnion.partner2_id : focusUnion.partner1_id)
      : null;
  }
  renderTree();
  updateFocusBanner();
}

export function setFocus(personId) {
  if (!S.FOCUS_PERSON_ID) {
    S.ORIGINAL_CENTER_ID_A = S.CENTER_ID_A;
    S.ORIGINAL_CENTER_ID_B = S.CENTER_ID_B;
  }
  S.FOCUS_PERSON_ID = personId;
  const sel = document.getElementById("focus-depth-select");
  const val = sel?.value || "1";
  S.FOCUS_DEPTH = val === "all" ? "all" : parseInt(val, 10);
  applyFocus();
}

export function clearFocus() {
  // No-op when not focused: the tree background click calls this
  // unconditionally, and re-applying focus state would both discard the
  // viewer's center and waste a full re-render.
  if (!S.FOCUS_PERSON_ID) return;
  S.FOCUS_PERSON_ID = null;
  applyFocus();
}

export function updateFocusBanner() {
  const banner = document.getElementById("focus-banner");
  if (!banner) return;
  if (!S.FOCUS_PERSON_ID) {
    banner.classList.add("hidden");
    return;
  }
  banner.classList.remove("hidden");
  const nameEl = document.getElementById("focus-banner-name");
  if (nameEl) nameEl.innerHTML = `<a class="person-link" data-person-id="${S.FOCUS_PERSON_ID}" href="javascript:void(0)">${personThumb(S.FOCUS_PERSON_ID, 20)} ${personName(S.FOCUS_PERSON_ID)}</a>`;
  const sel = document.getElementById("focus-depth-select");
  if (sel) sel.value = S.FOCUS_DEPTH === "all" ? "all" : String(S.FOCUS_DEPTH);
}

// ═══════════════════════════════════════════════════════════════
// Person Detail Panel
// ═══════════════════════════════════════════════════════════════


// ── Wire tree zoom/pan controls + keyboard (static elements, wired once) ──
document.getElementById("tree-zoom-in")?.addEventListener("click", () => zoomTreeBy(1.3));
document.getElementById("tree-zoom-out")?.addEventListener("click", () => zoomTreeBy(1 / 1.3));
document.getElementById("tree-fit")?.addEventListener("click", () => fitTreeToScreen());
document.getElementById("tree-center-me")?.addEventListener("click", () => centerTreeOnMe());

// Tree depth (complexity) segmented control
const _treeDepthBar = document.querySelector(".tree-depth-bar");
if (_treeDepthBar) {
  for (const btn of _treeDepthBar.querySelectorAll(".tree-depth-btn")) {
    if (parseInt(btn.dataset.depth, 10) === S.TREE_DEPTH) {
      btn.classList.add("active");
      btn.setAttribute("aria-checked", "true");
    } else {
      btn.classList.remove("active");
      btn.setAttribute("aria-checked", "false");
    }
    btn.addEventListener("click", () => {
      S.TREE_DEPTH = parseInt(btn.dataset.depth, 10);
      localStorage.setItem("ft-tree-depth", String(S.TREE_DEPTH));
      for (const b of _treeDepthBar.querySelectorAll(".tree-depth-btn")) {
        b.classList.toggle("active", b === btn);
        b.setAttribute("aria-checked", b === btn ? "true" : "false");
      }
      renderTree();
    });
  }
}

const _treeContainerEl = document.querySelector(".tree-container");
_treeContainerEl?.addEventListener("keydown", (e) => {
  if (!_treeSvg || !_treeZoom) return;
  const pan = 80;
  let handled = true;
  if (e.key === "ArrowUp") _treeSvg.transition().duration(150).call(_treeZoom.translateBy, 0, pan);
  else if (e.key === "ArrowDown") _treeSvg.transition().duration(150).call(_treeZoom.translateBy, 0, -pan);
  else if (e.key === "ArrowLeft") _treeSvg.transition().duration(150).call(_treeZoom.translateBy, pan, 0);
  else if (e.key === "ArrowRight") _treeSvg.transition().duration(150).call(_treeZoom.translateBy, -pan, 0);
  else if (e.key === "+" || e.key === "=") zoomTreeBy(1.3);
  else if (e.key === "-" || e.key === "_") zoomTreeBy(1 / 1.3);
  else if (e.key.toLowerCase() === "f") fitTreeToScreen();
  else handled = false;
  if (handled) e.preventDefault();
});

// ── SVG Download ──────────────────────────────────────────────────────────────

document.getElementById("tree-download-svg")?.addEventListener("click", () => {
  const svgEl = document.getElementById("tree-svg");
  if (!svgEl) return;

  // Capture current bounding box to set width/height on the output
  const bbox = svgEl.getBBox ? svgEl.getBBox() : null;
  const vb = svgEl.getAttribute("viewBox");
  const width = svgEl.getAttribute("width") || (bbox ? Math.ceil(bbox.width + 40) : 1200);
  const height = svgEl.getAttribute("height") || (bbox ? Math.ceil(bbox.height + 40) : 800);

  // Clone so we can add xmlns and a white background without mutating the live DOM
  const clone = svgEl.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  clone.setAttribute("width", width);
  clone.setAttribute("height", height);
  if (!vb && bbox) {
    clone.setAttribute("viewBox", `${bbox.x - 20} ${bbox.y - 20} ${Number(width)} ${Number(height)}`);
  }

  // Prepend a white background rect
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("width", "100%");
  bg.setAttribute("height", "100%");
  bg.setAttribute("fill", "white");
  clone.insertBefore(bg, clone.firstChild);

  const serializer = new XMLSerializer();
  const svgString = serializer.serializeToString(clone);
  const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "family-tree.svg";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});
