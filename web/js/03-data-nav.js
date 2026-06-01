// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

export async function loadData() {
  const resp = await fetch("/api/data");
  if (!resp.ok) throw new Error(`Failed to load family data (HTTP ${resp.status})`);
  S.DATA = await resp.json();
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
      person._profilePhotoPath = profilePath || (person.photo_paths || [])[0] || null;
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
      if (person) person._profilePhotoPath = (person.photo_paths || [])[0] || null;
    }
  }
}

export function personName(id) {
  return S.PEOPLE_MAP[id]?.fullName || id;
}

/**
 * Return an HTML string for a small circular photo thumbnail.
 * Falls back to a colored initial-letter placeholder.
 * @param {string} id - person ID
 * @param {number} [size=24] - pixel size
 */
export function personLink(id, label) {
  const name = label || personName(id);
  return `<a class="person-link" data-person-id="${id}" href="javascript:void(0)">${name}</a>`;
}

export function croppedImg(src, alt, size, crop, cssClass) {
  if (!crop) {
    return `<img class="${cssClass || 'person-thumb'}" src="/${src}" alt="${alt}" style="width:${size}px;height:${size}px" loading="lazy" />`;
  }
  const scale = 1 / crop.w;
  const tx = -crop.x * scale * size;
  const ty = -crop.y * scale * size;
  return `<div class="cropped-thumb ${cssClass || ''}" style="width:${size}px;height:${size}px;border-radius:50%;overflow:hidden;position:relative;display:inline-block;flex-shrink:0"><img src="/${src}" alt="${alt}" style="position:absolute;width:${size * scale}px;height:auto;left:${tx}px;top:${ty}px" loading="lazy" /></div>`;
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

export function closePersonPanel() {
  document.getElementById("person-panel").classList.add("hidden");
  d3.selectAll(".node-group").classed("selected", false);
  if (S.MAP) setTimeout(() => S.MAP.invalidateSize(), 250);
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
