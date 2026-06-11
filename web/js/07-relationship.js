// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

export function populateRelSelectors() {
  const sorted = Object.values(S.PEOPLE_MAP).sort((a, b) =>
    a.fullName.localeCompare(b.fullName)
  );
  setupPersonPicker("picker-a", sorted, computeRelationship);
  setupPersonPicker("picker-b", sorted, computeRelationship);
  renderRelSuggestions();
}

export function setupPersonPicker(pickerId, people, onChange) {
  const container = document.getElementById(pickerId);
  const input = container.querySelector(".picker-search");
  const list = container.querySelector(".picker-list");
  container._selectedId = null;
  let current = [];
  let active = -1;

  function select(p) {
    if (container._selectedId === p.id) {
      container._selectedId = null;
      input.value = "";
      input.dataset.locked = "";
      active = -1;
      renderList("");
    } else {
      container._selectedId = p.id;
      input.value = p.fullName;
      input.dataset.locked = p.fullName;
    }
    list.classList.add("hidden"); // a choice was made — collapse the dropdown
    onChange();
  }

  function highlight() {
    [...list.children].forEach((el, i) =>
      el.classList.toggle("picker-item-active", i === active)
    );
    if (active >= 0 && list.children[active]) {
      list.children[active].scrollIntoView({ block: "nearest" });
    }
  }

  // Use the shared ranked matcher (name / maiden name / nicknames / years).
  function renderList(filter) {
    current = rankPeople(filter, people, 50);
    list.innerHTML = "";
    current.forEach((p) => {
      const item = document.createElement("div");
      item.className =
        "picker-item" + (p.id === container._selectedId ? " picker-item-selected" : "");
      item.dataset.id = p.id;
      item.innerHTML = personThumb(p.id, 24);
      const nameSpan = document.createElement("span");
      nameSpan.className = "picker-item-name";
      nameSpan.textContent = p.fullName;
      item.appendChild(nameSpan);
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        select(p);
      });
      list.appendChild(item);
    });
    highlight();
  }

  input.addEventListener("input", () => {
    if (input.value !== input.dataset.locked) {
      container._selectedId = null;
      input.dataset.locked = "";
      onChange();
    }
    active = -1;
    renderList(input.value);
    list.classList.remove("hidden");
  });

  // Combobox behavior: the list stays collapsed until the field is focused,
  // so the view isn't dominated by two full rosters on load.
  input.addEventListener("focus", () => {
    active = -1;
    renderList(input.value === input.dataset.locked ? "" : input.value);
    list.classList.remove("hidden");
  });
  input.addEventListener("blur", () => {
    setTimeout(() => list.classList.add("hidden"), 150);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      active = Math.min(active + 1, current.length - 1);
      highlight();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(active - 1, 0);
      highlight();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = current[active >= 0 ? active : 0];
      if (pick) select(pick);
    }
  });

  renderList("");
  list.classList.add("hidden"); // collapsed until focused
}

// Suggested "quick relationship" chips shown in the empty state: the current
// viewer paired with a small varied sample of relatives. One click computes it.
export function renderRelSuggestions() {
  const wrap = document.getElementById("rel-suggestions");
  if (!wrap) return;
  const anchor = S.CENTER_ID_A;
  const anchorP = anchor && S.PEOPLE_MAP[anchor];
  if (!anchorP) { wrap.innerHTML = ""; return; }

  const others = Object.values(S.PEOPLE_MAP).filter(p => p.id !== anchor && p.fullName);
  if (!others.length) { wrap.innerHTML = ""; return; }

  const picks = [];
  const byBirth = others.filter(p => p.birth_date).sort((a, b) => a.birth_date.localeCompare(b.birth_date));
  if (byBirth[0]) picks.push(byBirth[0]); // earliest-born ancestor — usually a fun result
  const byName = [...others].sort((a, b) => a.fullName.localeCompare(b.fullName));
  const step = Math.max(1, Math.floor(byName.length / 4));
  for (let i = 0; i < byName.length && picks.length < 4; i += step) {
    const p = byName[i];
    if (p.id !== anchor && !picks.some(x => x.id === p.id)) picks.push(p);
  }

  let html = `<div class="rel-suggest-label">Quick relationships from ${escapeHtml(anchorP.fullName)}</div><div class="rel-suggest-chips">`;
  for (const p of picks) {
    html += `<button class="rel-suggest-chip" data-a="${anchor}" data-b="${p.id}">
      ${personThumb(anchor, 26)}<span class="rel-suggest-x">&#8596;</span>${personThumb(p.id, 26)}
      <span class="rel-suggest-name">${escapeHtml(p.fullName)}</span>
    </button>`;
  }
  html += `</div>`;
  wrap.innerHTML = html;
  wrap.querySelectorAll(".rel-suggest-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      prefillRelPickers(btn.dataset.a, btn.dataset.b);
      computeRelationship();
    });
  });
}

export function computeRelationship() {
  const pickerA = document.getElementById("picker-a");
  const pickerB = document.getElementById("picker-b");
  const idA = (pickerA && pickerA._selectedId) || "";
  const idB = (pickerB && pickerB._selectedId) || "";
  const result = document.getElementById("rel-result");
  const empty = document.getElementById("rel-empty");

  if (!idA || !idB) {
    result.classList.add("hidden");
    if (empty) empty.classList.remove("hidden"); // show suggestions until both picked
    return;
  }

  if (empty) empty.classList.add("hidden");

  if (idA && idB) {
    router.navigate(`/relationships/${idA}/${idB}`, { replace: true });
  }

  result.classList.remove("hidden");

  // The hero: both people, side by side, connected. Shared across all outcomes.
  const peopleRow = `
    <div class="rel-people">
      <a class="rel-person person-link" data-person-id="${idA}" href="javascript:void(0)">${personThumb(idA, 64)}<span>${personName(idA)}</span></a>
      <span class="rel-connector-arrow" aria-hidden="true">&#8596;</span>
      <a class="rel-person person-link" data-person-id="${idB}" href="javascript:void(0)">${personThumb(idB, 64)}<span>${personName(idB)}</span></a>
    </div>`;

  if (idA === idB) {
    result.innerHTML = `${peopleRow}<p class="rel-statement">That's the same person.</p>`;
    return;
  }

  // Client-side relationship calculation (simplified LCA)
  const label = calculateRelationship(idA, idB);
  const path = relationshipPath(idA, idB);
  const steps = path && path.length > 1 ? path.length - 1 : 0;
  const pathBtn = steps
    ? `<button class="rel-show-path" onclick="showRelationshipPath('${idA}', '${idB}')">Show path on tree · ${steps} step${steps === 1 ? "" : "s"}</button>`
    : "";

  // The label describes B's relationship to A (gender/role keyed on B), so the
  // natural-language statement reads "B is A's <label>".
  const statement = label === "no relation found"
    ? `<p class="rel-statement">No blood or marriage relation found between <strong>${personName(idA)}</strong> and <strong>${personName(idB)}</strong>.</p>`
    : `<p class="rel-statement"><strong>${personName(idB)}</strong> is <strong>${personName(idA)}</strong>'s <span class="rel-statement-label">${formatRelLabel(label)}</span></p>`;

  result.innerHTML = `${peopleRow}${statement}${pathBtn}`;
}

// Viewer-relative relationship text for profile pills / hovercards. Keyed off
// S.VIEWER_ID (who the user IS), never the tree center — focus mode and layout
// fallbacks move S.CENTER_ID_A, which used to shift every pill by generations
// (a daughter labeled "great-granddaughter" relative to a focused ancestor).
// Says "Your X" only when the viewer is the signed-in person (or an explicit
// viewing-as choice); otherwise names the reference person to stay honest.
export function viewerRelationText(personId) {
  const viewerId = S.VIEWER_ID || S.CENTER_ID_A;
  if (!viewerId || personId === viewerId) return null;
  const label = calculateRelationship(viewerId, personId);
  if (!label || label === "no relation found") return null;
  const authPid = S.AUTH_USER?.person_id;
  const isSelf = authPid ? viewerId === authPid : !!S.VIEWER_ID;
  if (isSelf) return `Your ${formatRelLabel(label)}`;
  const viewer = S.PEOPLE_MAP[viewerId];
  const first = (viewer?.given_name || viewer?.fullName || "viewer").split(/\s+/)[0];
  return `${escapeHtml(first)}'s ${formatRelLabel(label)}`;
}

// Collapse a long "great-great-…-grandparent" chain into the genealogy-standard
// compact form ("7× great-granddaughter") for display. Three or more "great-"s
// is where spelling it out starts to wrap and lose meaning.
export function formatRelLabel(label) {
  const m = label.match(/^((?:great-){3,})grand(father|mother|parent|son|daughter|child)$/i);
  if (m) {
    const greats = m[1].match(/great-/gi).length;
    return `${greats}× great-grand${m[2].toLowerCase()}`;
  }
  return label;
}

// Shortest path between two people over the family graph (parent-child + spouse
// edges, undirected). Returns an ordered array of person ids, or null.
export function relationshipPath(idA, idB) {
  if (!idA || !idB) return null;
  if (idA === idB) return [idA];
  const src = S.ORIGINAL_DATA || S.DATA;
  const adj = {};
  const add = (a, b) => { (adj[a] = adj[a] || []).push(b); };
  for (const r of src.relationships) { add(r.parent_id, r.child_id); add(r.child_id, r.parent_id); }
  for (const u of src.unions) { add(u.partner1_id, u.partner2_id); add(u.partner2_id, u.partner1_id); }
  const prev = { [idA]: null };
  const queue = [idA];
  while (queue.length) {
    const cur = queue.shift();
    if (cur === idB) {
      const path = [];
      for (let n = idB; n != null; n = prev[n]) path.unshift(n);
      return path;
    }
    for (const nb of adj[cur] || []) {
      if (!(nb in prev)) { prev[nb] = cur; queue.push(nb); }
    }
  }
  return null;
}

// Switch to the tree and highlight the relationship path between two people.
export function showRelationshipPath(idA, idB) {
  const path = relationshipPath(idA, idB);
  if (!path || path.length < 2) return;
  switchTab("tree");
  // Show the full tree (clear any focus filter) so all path nodes are present.
  if (S.FOCUS_PERSON_ID && typeof clearFocus === "function") clearFocus();
  router.navigate("/tree");
  setTimeout(() => highlightTreePath(path), 150);
}

export function calculateRelationship(idA, idB) {
  // Build parent map
  const parentsOf = {};
  for (const r of S.DATA.relationships) {
    if (!parentsOf[r.child_id]) parentsOf[r.child_id] = [];
    parentsOf[r.child_id].push(r.parent_id);
  }

  // Build spouses map and union lookup
  const spousesOf = {};
  const unionLookup = {};
  for (const u of S.DATA.unions) {
    if (!spousesOf[u.partner1_id]) spousesOf[u.partner1_id] = [];
    if (!spousesOf[u.partner2_id]) spousesOf[u.partner2_id] = [];
    spousesOf[u.partner1_id].push(u.partner2_id);
    spousesOf[u.partner2_id].push(u.partner1_id);
    const key = [u.partner1_id, u.partner2_id].sort().join("|");
    unionLookup[key] = u;
  }

  function ancestorsWithDist(pid) {
    const dist = { [pid]: 0 };
    const queue = [pid];
    while (queue.length > 0) {
      const current = queue.shift();
      for (const parent of parentsOf[current] || []) {
        if (!(parent in dist)) {
          dist[parent] = dist[current] + 1;
          queue.push(parent);
        }
      }
    }
    return dist;
  }

  function bloodOnly(fromId, toId) {
    if (fromId === toId) return null; // same person is not a blood *relation*
    const ancA = ancestorsWithDist(fromId);
    const ancB = ancestorsWithDist(toId);
    const common = [];
    for (const id in ancA) {
      if (id in ancB) common.push([id, ancA[id], ancB[id]]);
    }
    common.sort((a, b) => a[1] + a[2] - (b[1] + b[2]));
    if (common.length === 0) return null;
    const [, dA, dB] = common[0];
    const g = S.PEOPLE_MAP[toId]?.gender || "unknown";
    if (dA === 0) return descendantLabel(dB, g);
    if (dB === 0) return ancestorLabel(dA, g);
    if (dA === 1 && dB === 1) return g === "male" ? "brother" : g === "female" ? "sister" : "sibling";
    if (dA === 1 && dB === 2) return g === "male" ? "nephew" : g === "female" ? "niece" : "niece/nephew";
    if (dA === 2 && dB === 1) return g === "male" ? "uncle" : g === "female" ? "aunt" : "uncle/aunt";
    const degree = Math.min(dA, dB) - 1;
    const removed = Math.abs(dA - dB);
    const ordinals = ["", "first", "second", "third", "fourth", "fifth"];
    let lbl = `${ordinals[degree] || degree + "th"} cousin`;
    if (removed > 0) lbl += removed === 1 ? " once removed" : removed === 2 ? " twice removed" : ` ${removed} times removed`;
    return lbl;
  }

  // 1. Blood relation
  const blood = bloodOnly(idA, idB);
  if (blood) return blood;

  const gA = S.PEOPLE_MAP[idA]?.gender || "unknown";
  const gB = S.PEOPLE_MAP[idB]?.gender || "unknown";
  const unionEnded = (x, y) => {
    const u = unionLookup[[x, y].sort().join("|")];
    return !!(u && (u.end_date || u.end_reason));
  };
  // Current marriages first: a relation through a standing union should win
  // over one through a dissolved union when someone has both.
  const byEnded = (pid) =>
    [...(spousesOf[pid] || [])].sort((a, b) => unionEnded(pid, a) - unionEnded(pid, b));
  const spA = byEnded(idA);
  const spB = byEnded(idB);

  // 2. Direct spouse / ex-spouse
  if (spA.includes(idB)) {
    if (unionEnded(idA, idB)) return gB === "male" ? "ex-husband" : gB === "female" ? "ex-wife" : "ex-spouse";
    return gB === "male" ? "husband" : gB === "female" ? "wife" : "spouse";
  }

  // 3. B is A's spouse's blood relative → in-law. Through a dissolved union
  // there is no standing in-law/step relation — describe it instead
  // ("ex-wife's aunt"), never e.g. "stepson" via a marriage that ended.
  for (const sA of spA) {
    const lbl = bloodOnly(sA, idB);
    if (lbl) {
      if (unionEnded(idA, sA)) {
        const gS = S.PEOPLE_MAP[sA]?.gender || "unknown";
        const sp = gS === "male" ? "ex-husband" : gS === "female" ? "ex-wife" : "ex-spouse";
        return `${sp}'s ${lbl}`;
      }
      const inLaw = toInLaw(lbl);
      if (inLaw) return inLaw;
    }
  }

  // 4. A is B's spouse's blood relative → reverse in-law; dissolved unions are
  // described ("father's ex-wife", "sister's ex-husband") rather than mapped.
  for (const sB of spB) {
    const lbl = bloodOnly(idA, sB);
    if (lbl) {
      if (unionEnded(idB, sB)) {
        const sp = gB === "male" ? "ex-husband" : gB === "female" ? "ex-wife" : "ex-spouse";
        return `${lbl}'s ${sp}`;
      }
      const inLaw = reverseInLaw(lbl, gB);
      if (inLaw) return inLaw;
    }
  }

  // 5. A's spouse's blood relative is B's spouse → co-in-law (e.g. wife's sister's husband)
  for (const sA of spA) {
    for (const sB of spB) {
      if (sA === sB) {
        // Same spouse on both sides (a current wife and an ex-wife of the
        // same person): "husband's ex-wife", not a bloodOnly self-lookup.
        const gS = S.PEOPLE_MAP[sA]?.gender || "unknown";
        const wordS = gS === "male" ? "husband" : gS === "female" ? "wife" : "spouse";
        const wordB = gB === "male" ? "husband" : gB === "female" ? "wife" : "spouse";
        const exA = unionEnded(idA, sA) ? "ex-" : "";
        const exB = unionEnded(idB, sB) ? "ex-" : "";
        return `${exA}${wordS}'s ${exB}${wordB}`;
      }
      const lbl = bloodOnly(sA, sB);
      if (lbl) {
        const wA = gA === "male" ? "wife" : gA === "female" ? "husband" : "spouse";
        const wB = gB === "male" ? "husband" : gB === "female" ? "wife" : "spouse";
        return `${wA}'s ${lbl}'s ${wB}`;
      }
    }
  }

  return "no relation found";
}

// B is A's spouse's blood <lbl> → what is B to A?
export function toInLaw(lbl) {
  const map = {
    "father": "father-in-law", "mother": "mother-in-law", "parent": "parent-in-law",
    "brother": "brother-in-law", "sister": "sister-in-law", "sibling": "sibling-in-law",
    "grandfather": "grandfather-in-law", "grandmother": "grandmother-in-law", "grandparent": "grandparent-in-law",
    "uncle": "uncle-in-law", "aunt": "aunt-in-law", "uncle/aunt": "uncle/aunt-in-law",
    "nephew": "nephew-in-law", "niece": "niece-in-law", "niece/nephew": "niece/nephew-in-law",
    // spouse's child who isn't also A's blood child (blood wins earlier)
    "son": "stepson", "daughter": "stepdaughter", "child": "stepchild",
  };
  if (map[lbl]) return map[lbl];
  if (lbl.includes("cousin")) return lbl + "-in-law";
  if (/great-.*grand(father|mother|parent)/.test(lbl)) return lbl + "-in-law";
  return null;
}

// A is B's spouse's blood <lbl> → what is B to A? (lbl describes B's spouse
// relative to A; gB is B's gender.) Blood relations win before this runs, so
// e.g. "father's wife" here really is a step-mother, not the blood mother.
export function reverseInLaw(lbl, gB) {
  if (lbl === "son" || lbl === "daughter" || lbl === "child")
    return gB === "male" ? "son-in-law" : gB === "female" ? "daughter-in-law" : "child-in-law";
  if (lbl === "father" || lbl === "mother" || lbl === "parent")
    return gB === "male" ? "stepfather" : gB === "female" ? "stepmother" : "step-parent";
  if (lbl === "brother" || lbl === "sister" || lbl === "sibling")
    return gB === "male" ? "brother-in-law" : gB === "female" ? "sister-in-law" : "sibling-in-law";
  if (lbl === "nephew" || lbl === "niece" || lbl === "niece/nephew")
    return gB === "male" ? "nephew-in-law" : gB === "female" ? "niece-in-law" : "niece/nephew-in-law";
  if (lbl === "uncle" || lbl === "aunt" || lbl === "uncle/aunt")
    return gB === "male" ? "uncle-in-law" : gB === "female" ? "aunt-in-law" : "uncle/aunt-in-law";
  if (lbl === "grandson" || lbl === "granddaughter" || lbl === "grandchild")
    return gB === "male" ? "grandson-in-law" : gB === "female" ? "granddaughter-in-law" : "grandchild-in-law";
  if (lbl.includes("cousin")) return lbl + "-in-law";
  return null;
}

export function ancestorLabel(gen, gender) {
  if (gen === 1) return gender === "male" ? "father" : gender === "female" ? "mother" : "parent";
  if (gen === 2) return gender === "male" ? "grandfather" : gender === "female" ? "grandmother" : "grandparent";
  const prefix = "great-".repeat(gen - 2);
  return gender === "male" ? `${prefix}grandfather` : gender === "female" ? `${prefix}grandmother` : `${prefix}grandparent`;
}

export function descendantLabel(gen, gender) {
  if (gen === 1) return gender === "male" ? "son" : gender === "female" ? "daughter" : "child";
  if (gen === 2) return gender === "male" ? "grandson" : gender === "female" ? "granddaughter" : "grandchild";
  const prefix = "great-".repeat(gen - 2);
  return gender === "male" ? `${prefix}grandson` : gender === "female" ? `${prefix}granddaughter` : `${prefix}grandchild`;
}

// ═══════════════════════════════════════════════════════════════
// Map View (Leaflet)
// ═══════════════════════════════════════════════════════════════

