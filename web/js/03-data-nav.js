// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

// ── Relationship visibility (client-side declutter) ────────────────────
// A parent-child link can be tagged: "everyone" (default), "extended"
// (visible to the family circle + cousins/aunts/uncles), or
// "self_and_children" / "Family" (direct ancestors, siblings, children,
// nieces/nephews). This is a UI declutter keyed off the current viewer
// (S.CENTER_ID_A — the "viewing as" person), not a security boundary; the
// full graph always stays in S.ORIGINAL_DATA.

// Compute the viewer's kinship circles from the FULL relationship set.
function _kinCircles(viewerId) {
  const rels = (S.ORIGINAL_DATA && S.ORIGINAL_DATA.relationships) || [];
  const parentsOf = {}, childrenOf = {};
  for (const r of rels) {
    (parentsOf[r.child_id] ||= []).push(r.parent_id);
    (childrenOf[r.parent_id] ||= []).push(r.child_id);
  }
  const ps = id => parentsOf[id] || [];
  const cs = id => childrenOf[id] || [];

  const family = new Set([viewerId]);
  // Direct ancestors (walk parents up).
  let frontier = [viewerId];
  const seen = new Set([viewerId]);
  while (frontier.length) {
    const next = [];
    for (const x of frontier) for (const p of ps(x)) if (!seen.has(p)) { seen.add(p); family.add(p); next.push(p); }
    frontier = next;
  }
  const myParents = ps(viewerId);
  // Siblings (other children of my parents) and my own children.
  const siblings = new Set();
  for (const p of myParents) for (const sib of cs(p)) { family.add(sib); if (sib !== viewerId) siblings.add(sib); }
  for (const ch of cs(viewerId)) family.add(ch);
  // Nieces/nephews (children of siblings).
  for (const sib of siblings) for (const n of cs(sib)) family.add(n);

  // Extended = family + aunts/uncles (parents' siblings) + their children (cousins).
  const extended = new Set(family);
  for (const p of myParents) for (const gp of ps(p)) {
    for (const auntUncle of cs(gp)) {
      if (myParents.includes(auntUncle)) continue;
      extended.add(auntUncle);
      for (const cousin of cs(auntUncle)) extended.add(cousin);
    }
  }
  return { family, extended };
}

// Rebuild S.DATA from S.ORIGINAL_DATA, hiding links the current viewer
// shouldn't see. Call after the viewer changes (and once at startup).
export function applyVisibilityFilter() {
  const full = S.ORIGINAL_DATA;
  if (!full || !full.relationships) return;
  const viewerId = S.CENTER_ID_A || null;
  const { family, extended } = viewerId
    ? _kinCircles(viewerId)
    : { family: new Set(), extended: new Set() };

  const relationships = full.relationships.filter((r) => {
    const v = r.visibility || "everyone";
    if (v === "everyone") return true;
    const inFamily = family.has(r.parent_id) || family.has(r.child_id);
    if (v === "self_and_children") return inFamily;
    if (v === "extended") return inFamily || extended.has(r.parent_id) || extended.has(r.child_id);
    return true;
  });

  S.DATA = { ...full, relationships };
}

export async function loadData() {
  const resp = await fetch("/api/data");
  if (!resp.ok) throw new Error(`Failed to load family data (HTTP ${resp.status})`);
  S.DATA = await resp.json();
  // Update undo button visibility after every data load (fire-and-forget).
  refreshUndoStatus();
  S.PEOPLE_MAP = {};
  for (const p of S.DATA.people) {
    const name = [p.given_name, p.surname].filter(Boolean).join(" ") || p.surname;
    S.PEOPLE_MAP[p.id] = { ...p, fullName: name.trim() };
  }
  S.ORIGINAL_DATA = S.DATA;

  // Build S.PHOTOS_MAP from S.DATA.photos and compute _profilePhotoPath for each person
  S.PHOTOS_MAP = {};
  if (S.DATA.photos) {
    for (const photo of S.DATA.photos) {
      S.PHOTOS_MAP[photo.file_path] = photo;
    }
    // Compute _profilePhotoPath for each person
    for (const p of S.DATA.people) {
      const person = S.PEOPLE_MAP[p.id];
      if (!person) continue;
      // Find their profile photo from the photos data
      let profilePath = null;
      if (S.DATA.photos) {
        for (const photo of S.DATA.photos) {
          for (const tp of photo.tagged_people || []) {
            if (tp.person_id === p.id && tp.is_profile) {
              profilePath = photo.file_path;
              break;
            }
          }
          if (profilePath) break;
        }
      }
      person._profilePhotoPath = profilePath || null;
      // Compute _profileCrop from the matching tagged_people entry
      person._profileCrop = null;
      if (person._profilePhotoPath && S.DATA.photos) {
        const profilePhoto = S.PHOTOS_MAP[person._profilePhotoPath];
        if (profilePhoto) {
          const tp = (profilePhoto.tagged_people || []).find(t => t.person_id === p.id && t.is_profile);
          if (tp && tp.crop_x != null && tp.crop_w != null) {
            person._profileCrop = { x: tp.crop_x, y: tp.crop_y, w: tp.crop_w, h: tp.crop_h };
          }
        }
      }
    }
  } else {
    for (const p of S.DATA.people) {
      const person = S.PEOPLE_MAP[p.id];
      if (person) person._profilePhotoPath = null;
    }
  }
}

// Escape user-supplied text before interpolating it into innerHTML/template
// HTML. Use everywhere a person field (name, caption, note, place, …) is put
// into markup, to prevent stored XSS from free-text fields.
export function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ── Dates ───────────────────────────────────────────────────────────────
// Dates are stored as ISO strings at three precisions (YYYY, YYYY-MM,
// YYYY-MM-DD). These are the single place the frontend turns one into a year or
// a sort key, so a stray non-ISO value can't silently break timeline placement,
// age math, or ordering across the ~30 call sites that used to inline this.

// Integer year from an ISO-ish date, or null. Tolerates leading noise so a
// stray "~1622" still yields 1622 rather than NaN.
export function dateYear(d) {
  if (!d) return null;
  const m = /(\d{4})/.exec(String(d));
  return m ? parseInt(m[1], 10) : null;
}

// A lexicographically-sortable key for an ISO-ish date. Undated sorts last by
// default (pass placeEmptyFirst=true for the few ascending lists that want
// blanks at the top). Extracts the ISO core so non-ISO junk still sorts by year.
export function dateSortKey(d, placeEmptyFirst = false) {
  if (!d) return placeEmptyFirst ? "" : "9999";
  const m = /(\d{4}(?:-\d{2}(?:-\d{2})?)?)/.exec(String(d));
  return m ? m[1] : placeEmptyFirst ? "" : "9999";
}

// Returns an HTML-escaped display name (safe to interpolate into markup). All
// current callers render the result as HTML.
export function personName(id) {
  return escapeHtml(S.PEOPLE_MAP[id]?.fullName || id);
}

/**
 * Return an HTML string for a small circular photo thumbnail.
 * Falls back to a colored initial-letter placeholder.
 * @param {string} id - person ID
 * @param {number} [size=24] - pixel size
 */
export function personLink(id, label) {
  const name = label ? escapeHtml(label) : personName(id);
  return `<a class="person-link" data-person-id="${id}" href="javascript:void(0)">${name}</a>`;
}

export function croppedImg(src, alt, size, crop, cssClass) {
  const a = escapeHtml(alt);
  if (!crop) {
    return `<img class="${cssClass || 'person-thumb'}" src="/${src}" alt="${a}" style="width:${size}px;height:${size}px" loading="lazy" />`;
  }
  const scale = 1 / crop.w;
  const tx = -crop.x * scale * size;
  const ty = -crop.y * scale * size;
  return `<div class="cropped-thumb ${cssClass || ''}" style="width:${size}px;height:${size}px;border-radius:50%;overflow:hidden;position:relative;display:inline-block;flex-shrink:0"><img src="/${src}" alt="${a}" style="position:absolute;width:${size * scale}px;height:auto;left:${tx}px;top:${ty}px" loading="lazy" /></div>`;
}

export function personThumb(id, size = 24) {
  const person = S.PEOPLE_MAP[id];
  if (!person) return "";
  const src = person._profilePhotoPath;
  if (src) {
    return croppedImg(src, person.fullName, size, person._profileCrop, "person-thumb");
  }
  const initial = (person.given_name || "?")[0].toUpperCase();
  const cls = person.gender === "female" ? "female" : "male";
  return `<div class="person-thumb-placeholder ${cls}" style="width:${size}px;height:${size}px;font-size:${Math.round(size * 0.45)}px">${initial}</div>`;
}

// ═══════════════════════════════════════════════════════════════
// Router — path-based deep linking
// ═══════════════════════════════════════════════════════════════

export class Router {
  constructor() {
    this.routes = [];
    this._current = null;   // { route, params, query }
    this._suppress = false; // when true, enter() handlers must not push history
    window.addEventListener("popstate", () => this._onPopState());
  }

  register(pattern, handler) {
    const keys = [];
    let greedy = false;
    const regSrc = pattern.replace(/:([a-zA-Z_]+)\+?/g, (m, key) => {
      keys.push(key);
      if (m.endsWith("+")) { greedy = true; return "(.+)"; }
      return "([^/]+)";
    });
    this.routes.push({
      pattern,
      regex: new RegExp("^" + regSrc + "$"),
      keys,
      greedy,
      layer: handler.layer || "base",
      enter: handler.enter,
      exit: handler.exit || null,
    });
  }

  navigate(path, { replace = false, query = {} } = {}) {
    if (this._suppress) return;
    const url = new URL(window.location);
    url.pathname = path;
    // Preserve ?me= across navigations; merge in any explicit query params
    const newParams = new URLSearchParams();
    const me = url.searchParams.get("me");
    if (me) newParams.set("me", me);
    for (const [k, v] of Object.entries(query)) {
      if (v != null && v !== "") newParams.set(k, v);
    }
    url.search = newParams.toString() ? "?" + newParams.toString() : "";

    // Track current route for exit() calls on next navigation
    const result = this.match(path);
    if (this._current?.route?.exit && this._current.route !== result?.route) {
      // Don't actually call exit — the caller has already handled the state change.
      // Exit is only called on popstate to clean up stale overlays.
    }
    this._current = result ? { route: result.route, params: result.params, query } : null;

    if (replace) {
      window.history.replaceState({}, "", url);
    } else {
      window.history.pushState({}, "", url);
    }
  }

  match(path) {
    for (const route of this.routes) {
      const m = path.match(route.regex);
      if (m) {
        const params = {};
        route.keys.forEach((key, i) => { params[key] = decodeURIComponent(m[i + 1]); });
        return { route, params };
      }
    }
    return null;
  }

  apply() {
    this._suppress = true;
    this._apply();
    this._suppress = false;
  }

  _apply() {
    const path = window.location.pathname;
    const query = Object.fromEntries(new URLSearchParams(window.location.search));

    // Exit current overlay/base route
    if (this._current?.route?.exit) {
      this._current.route.exit();
    }

    const result = this.match(path);
    if (result) {
      this._current = { route: result.route, params: result.params, query };
      result.route.enter(result.params, query);
    } else {
      // Default: show tree
      this._current = null;
      switchTab("tree");
    }
  }

  _onPopState() {
    this._suppress = true;
    this._apply();
    this._suppress = false;
  }
}

export const router = new Router();

// ═══════════════════════════════════════════════════════════════
// Tab Navigation
// ═══════════════════════════════════════════════════════════════

export function switchTab(viewName) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.remove("active");
    t.setAttribute("aria-selected", "false");
  });
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  const tab = document.querySelector(`.tab[data-view="${viewName}"]`);
  if (tab) {
    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
  }
  const view = document.getElementById(`view-${viewName}`);
  if (view) view.classList.add("active");
}

export function activeViewName() {
  const el = document.querySelector(".view.active");
  return el ? el.id.replace("view-", "") : "tree";
}

export function personRoutePrefix() {
  const v = activeViewName();
  return v === "tree" || v === "map" || v === "timeline" ? `/${v}` : "/tree";
}

// ─────────────────────────────────────────────────────────────
// Focus trap utility
// ─────────────────────────────────────────────────────────────

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Trap keyboard focus inside containerEl.
 * - Saves the previously focused element.
 * - Moves focus to the first focusable child.
 * - Keeps Tab / Shift+Tab cycling within the container.
 * - Returns a release() function that removes the listener and
 *   restores focus to the previously focused element.
 *
 * @param {Element} containerEl
 * @returns {{ release: () => void }}
 */
export function trapFocus(containerEl) {
  const previous = document.activeElement;

  function getFocusable() {
    return Array.from(containerEl.querySelectorAll(FOCUSABLE)).filter(
      (el) => !el.closest("[hidden]") && el.offsetParent !== null
    );
  }

  // Move focus into the container
  const first = getFocusable()[0];
  if (first) first.focus();

  function onKeyDown(e) {
    if (e.key !== "Tab") return;
    const focusable = getFocusable();
    if (focusable.length === 0) { e.preventDefault(); return; }
    const firstEl = focusable[0];
    const lastEl = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      }
    } else {
      if (document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    }
  }

  containerEl.addEventListener("keydown", onKeyDown);

  function release() {
    containerEl.removeEventListener("keydown", onKeyDown);
    if (previous && typeof previous.focus === "function") {
      try { previous.focus(); } catch (_) {}
    }
  }

  return { release };
}

// Track the active focus-trap release function for the panel
let _panelFocusTrapRelease = null;

export function closePersonPanel() {
  const panel = document.getElementById("person-panel");
  panel.classList.remove("panel-open");
  setTimeout(() => panel.classList.add("hidden"), 200);
  d3.selectAll(".node-group").classed("selected", false);
  if (S.MAP) setTimeout(() => S.MAP.invalidateSize(), 250);
  if (_panelFocusTrapRelease) {
    _panelFocusTrapRelease();
    _panelFocusTrapRelease = null;
  }
}

// Called externally (from the global Esc handler) to install focus trap when
// the panel is opened by showPersonPanel() (which lives in 05-panel.js, which
// we cannot edit).
export function _installPanelFocusTrap() {
  const panel = document.getElementById("person-panel");
  if (!panel) return;
  if (_panelFocusTrapRelease) {
    _panelFocusTrapRelease();
    _panelFocusTrapRelease = null;
  }
  // Give the panel time to render its content before trapping
  setTimeout(() => {
    _panelFocusTrapRelease = trapFocus(panel).release;
  }, 50);
}

export function closeLightbox() {
  const lb = document.getElementById("lightbox");
  if (lb) lb.remove();
}

export function applyGalleryFiltersFromQuery(query) {
  if (query.year) {
    for (const v of query.year.split(",")) GALLERY_FILTERS.year.add(v);
  }
  if (query.place) {
    for (const v of query.place.split(",")) GALLERY_FILTERS.place.add(v);
  }
  if (query.tagged) {
    for (const v of query.tagged.split(",")) GALLERY_FILTERS.person.add(v);
  }
  if (query.status) {
    for (const v of query.status.split(",")) GALLERY_FILTERS.status.add(v);
  }
  renderPhotoGallery();
  renderGalleryFacets();
  renderActiveFilterPills();
}

export function prefillRelPickers(id1, id2) {
  const pickerA = document.getElementById("picker-a");
  const pickerB = document.getElementById("picker-b");
  if (!pickerA || !pickerB) return;
  const personA = S.PEOPLE_MAP[id1];
  const personB = S.PEOPLE_MAP[id2];
  if (personA) {
    pickerA._selectedId = id1;
    const inputA = pickerA.querySelector(".picker-search");
    if (inputA) { inputA.value = personA.fullName; inputA.dataset.locked = personA.fullName; }
  }
  if (personB) {
    pickerB._selectedId = id2;
    const inputB = pickerB.querySelector(".picker-search");
    if (inputB) { inputB.value = personB.fullName; inputB.dataset.locked = personB.fullName; }
  }
}

export function currentGalleryFilterQuery() {
  const q = {};
  if (GALLERY_FILTERS.year.size) q.year = [...GALLERY_FILTERS.year].join(",");
  if (GALLERY_FILTERS.place.size) q.place = [...GALLERY_FILTERS.place].join(",");
  if (GALLERY_FILTERS.person.size) q.tagged = [...GALLERY_FILTERS.person].join(",");
  if (GALLERY_FILTERS.status.size) q.status = [...GALLERY_FILTERS.status].join(",");
  return q;
}

// ── Route registrations ──────────────────────────────────────────

// Tree tab
router.register("/", {
  enter() { switchTab("tree"); },
});

router.register("/tree", {
  enter() { switchTab("tree"); },
});

// Person panel (overlay on tree)
router.register("/tree/person/:personId", {
  layer: "overlay",
  enter({ personId }) {
    switchTab("tree");
    if (S.PEOPLE_MAP[personId]) showPersonPanel(personId);
  },
  exit() { closePersonPanel(); },
});

// Focus mode
router.register("/tree/focus/:personId", {
  enter({ personId }) {
    switchTab("tree");
    if (S.PEOPLE_MAP[personId]) setFocus(personId);
  },
  exit() { clearFocus(); },
});

router.register("/tree/focus/:personId/:depth", {
  enter({ personId, depth }) {
    switchTab("tree");
    if (S.PEOPLE_MAP[personId]) {
      S.FOCUS_DEPTH = depth === "all" ? "all" : parseInt(depth, 10);
      setFocus(personId);
    }
  },
  exit() { clearFocus(); },
});

// Timeline
router.register("/timeline", {
  enter() { switchTab("timeline"); },
});

// Map
router.register("/map", {
  enter() { switchTab("map"); },
});

router.register("/map/person/:personId", {
  layer: "overlay",
  enter({ personId }) {
    switchTab("map");
    if (S.PEOPLE_MAP[personId]) showPersonPanel(personId);
  },
  exit() { closePersonPanel(); },
});

// Timeline + person panel
router.register("/timeline/person/:personId", {
  layer: "overlay",
  enter({ personId }) {
    switchTab("timeline");
    if (S.PEOPLE_MAP[personId]) showPersonPanel(personId);
  },
  exit() { closePersonPanel(); },
});

// Photos
router.register("/photos", {
  enter(params, query) {
    switchTab("photos");
    if (query.year || query.place || query.tagged || query.status) {
      applyGalleryFiltersFromQuery(query);
    }
  },
});

// Photos + lightbox
router.register("/photos/view/:path+", {
  layer: "overlay",
  enter({ path }) {
    switchTab("photos");
    const photoObj = S.DATA?.photos?.find(p => p.file_path === path);
    if (photoObj) openLightbox(`/${path}`, "", path);
  },
  exit() { closeLightbox(); },
});

// Relationships
router.register("/relationships", {
  enter() { switchTab("relationships"); },
});

router.register("/relationships/:id1/:id2", {
  enter({ id1, id2 }) {
    switchTab("relationships");
    prefillRelPickers(id1, id2);
    computeRelationship();
  },
});

// ── Tab click handlers (use router) ──────────────────────────────

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const view = tab.dataset.view;
    switchTab(view);
    const routeMap = { tree: "/tree", timeline: "/timeline", map: "/map", photos: "/photos", relationships: "/relationships" };
    router.navigate(routeMap[view] || "/");
  });
});

// ═══════════════════════════════════════════════════════════════
// Tree Visualization — Butterfly Layout (D3)
// ═══════════════════════════════════════════════════════════════

// Central couple IDs — set via family-config.json; auto-detected from data if absent


// ═══════════════════════════════════════════════════════════════
// Person search (shared ranked matcher + global header search)
// ═══════════════════════════════════════════════════════════════

// Rank a given list of people against a query. Matches across full name,
// maiden name, nicknames, and birth/death years; every token must match; ranks
// exact > full-prefix > word-prefix > substring. Empty query returns the list
// unchanged (capped to limit). Shared by the header search and the pickers.
export function rankPeople(query, people, limit = Infinity) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return limit === Infinity ? people : people.slice(0, limit);
  const tokens = q.split(/\s+/);
  const scored = [];
  for (const p of people) {
    const name = (p.fullName || "").toLowerCase();
    const extra = [p.maiden_name, ...(p.nicknames || [])].filter(Boolean).join(" ").toLowerCase();
    const years = [p.birth_date, p.death_date].filter(Boolean).join(" ").toLowerCase();
    const hay = `${name} ${extra} ${years}`;
    if (!tokens.every((tok) => hay.includes(tok))) continue;
    let score;
    if (name === q) score = 100;
    else if (name.startsWith(q)) score = 80;
    else if (name.split(/\s+/).some((w) => w.startsWith(tokens[0]))) score = 60;
    else if (name.includes(q)) score = 40;
    else score = 20;
    scored.push({ p, score });
  }
  scored.sort((a, b) => b.score - a.score || a.p.fullName.localeCompare(b.p.fullName));
  const out = scored.map((s) => s.p);
  return limit === Infinity ? out : out.slice(0, limit);
}

export function searchPeopleLocal(query, limit = 8) {
  if (!(query || "").trim()) return [];
  return rankPeople(query, Object.values(S.PEOPLE_MAP), limit);
}

// Global header search: type-to-find a person, arrow keys to navigate, Enter to
// open their panel on the tree.
(function initGlobalSearch() {
  const input = document.getElementById("global-search");
  const results = document.getElementById("global-search-results");
  if (!input || !results) return;

  let matches = [];
  let active = -1;

  function close() {
    results.classList.add("hidden");
    input.setAttribute("aria-expanded", "false");
    active = -1;
  }

  function render() {
    if (!matches.length) {
      results.innerHTML = `<div class="header-search-empty">No matches</div>`;
    } else {
      results.innerHTML = matches
        .map((p, i) => {
          const years = [p.birth_date, p.death_date].map((d) => (d ? String(d).slice(0, 4) : "")).join("–").replace(/^–|–$/g, "");
          return `<div class="header-search-item${i === active ? " active" : ""}" role="option" data-id="${p.id}" aria-selected="${i === active}">
            <span class="header-search-name">${personName(p.id)}</span>
            ${years ? `<span class="header-search-years">${years}</span>` : ""}
          </div>`;
        })
        .join("");
    }
    results.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
  }

  function choose(id) {
    if (!id) return;
    close();
    input.value = "";
    switchTab("tree");
    router.navigate(`/tree/person/${id}`);
    showPersonPanel(id);
    if (typeof centerTreeOnNode === "function") centerTreeOnNode(id);
  }

  input.addEventListener("input", () => {
    matches = searchPeopleLocal(input.value);
    active = -1;
    if (input.value.trim()) render();
    else close();
  });

  input.addEventListener("keydown", (e) => {
    if (results.classList.contains("hidden")) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      active = Math.min(active + 1, matches.length - 1);
      render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(active - 1, 0);
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(matches[active >= 0 ? active : 0]?.id);
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });

  results.addEventListener("mousedown", (e) => {
    const item = e.target.closest(".header-search-item");
    if (item) {
      e.preventDefault();
      choose(item.dataset.id);
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".header-search")) close();
  });
})();

// ═══════════════════════════════════════════════════════════════
// Undo — DB-backed undo for delete-person
// ═══════════════════════════════════════════════════════════════

const _undoBtn = document.getElementById("undo-btn");

async function _refreshUndoBtn() {
  try {
    const resp = await fetch("/api/undo/status");
    if (!resp.ok) return;
    const { available } = await resp.json();
    if (_undoBtn) _undoBtn.style.display = available ? "" : "none";
  } catch (_) {}
}

export async function triggerUndo() {
  try {
    const resp = await fetch("/api/undo", { method: "POST" });
    if (!resp.ok) {
      if (typeof showToast === "function") showToast("Undo failed.");
      return;
    }
    const data = await resp.json();
    if (!data.restored) {
      if (typeof showToast === "function") showToast("Nothing to undo.");
      _refreshUndoBtn();
      return;
    }
    // Standard post-mutation refresh (via the window bridge — 04b loads
    // after this module). The old inline sequence here called
    // autoComputeLanes() with no arguments, which wiped S.LANES.
    await window.afterMutate(null);
    _refreshUndoBtn();
    const name = data.name || data.person_id || "person";
    if (typeof showToast === "function") showToast(`Restored: ${name}`);
  } catch (_) {
    if (typeof showToast === "function") showToast("Undo failed.");
  }
}

if (_undoBtn) {
  _undoBtn.addEventListener("click", triggerUndo);
}

// Ctrl/Cmd+Z — only when focus is not in a text field.
document.addEventListener("keydown", (e) => {
  if (!e.key || e.key.toLowerCase() !== "z") return;
  if (!e.ctrlKey && !e.metaKey) return;
  const tag = document.activeElement?.tagName?.toLowerCase();
  if (tag === "input" || tag === "textarea" || document.activeElement?.isContentEditable) return;
  e.preventDefault();
  triggerUndo();
});

// Poll once on load, then refresh after every data load so the button
// reflects actual stack state. Exported so 99-main.js can call it after init.
export function refreshUndoStatus() { _refreshUndoBtn(); }

// ─────────────────────────────────────────────────────────────
// Global Escape key handler — closes the topmost open overlay/panel.
// Priority (highest first):
//   1. Photo picker (#photo-picker-overlay)
//   2. Doc review overlay (#doc-review-overlay)
//   3. Doc upload overlay (#doc-upload-overlay)
//   4. GEDCOM overlay (#gedcom-overlay)
//   5. Onboarding overlay (#onboarding-overlay)
//   6. Person panel (#person-panel)
// ─────────────────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;

  const photoPickerOverlay = document.getElementById("photo-picker-overlay");
  if (photoPickerOverlay && !photoPickerOverlay.classList.contains("hidden")) {
    // closePhotoPicker is bridged from 12-photos.js
    if (typeof closePhotoPicker === "function") closePhotoPicker();
    else photoPickerOverlay.classList.add("hidden");
    e.stopPropagation();
    return;
  }

  const docReviewOverlay = document.getElementById("doc-review-overlay");
  if (docReviewOverlay && !docReviewOverlay.classList.contains("hidden")) {
    docReviewOverlay.classList.add("hidden");
    e.stopPropagation();
    return;
  }

  const docUploadOverlay = document.getElementById("doc-upload-overlay");
  if (docUploadOverlay && !docUploadOverlay.classList.contains("hidden")) {
    docUploadOverlay.classList.add("hidden");
    e.stopPropagation();
    return;
  }

  const gedcomOverlay = document.getElementById("gedcom-overlay");
  if (gedcomOverlay && !gedcomOverlay.classList.contains("hidden")) {
    gedcomOverlay.classList.add("hidden");
    e.stopPropagation();
    return;
  }

  const onboardingOverlay = document.getElementById("onboarding-overlay");
  if (onboardingOverlay && !onboardingOverlay.classList.contains("hidden")) {
    onboardingOverlay.classList.add("hidden");
    e.stopPropagation();
    return;
  }

  const panel = document.getElementById("person-panel");
  if (panel && !panel.classList.contains("hidden") && panel.classList.contains("panel-open")) {
    closePersonPanel();
    router.navigate("/tree");
    e.stopPropagation();
    return;
  }
});
