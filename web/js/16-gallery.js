// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

export function setCenterPerson(personId) {
  if (!S.PEOPLE_MAP[personId]) return;
  S.CENTER_ID_A = personId;
  // Re-apply the viewer-relative visibility filter before anything reads S.DATA.
  applyVisibilityFilter();
  const union = S.DATA.unions.find(u => u.partner1_id === personId || u.partner2_id === personId);
  S.CENTER_ID_B = union
    ? (union.partner1_id === personId ? union.partner2_id : union.partner1_id)
    : personId;

  // Rebuild lanes for the new center couple's grandparents
  // Always auto-compute to match the current viewer
  autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);

  // Update header dynamically
  updateDynamicHeader(S.CENTER_ID_A, S.CENTER_ID_B);

  localStorage.setItem("ft-viewing-as", personId);
  const url = new URL(window.location);
  url.searchParams.set("me", personId);
  window.history.replaceState({}, "", url);

  // Sync global viewing-as dropdown
  const globalSelect = document.getElementById("viewing-as-global");
  if (globalSelect && globalSelect.value !== personId) globalSelect.value = personId;

  // Sync user-menu viewing-as dropdown
  const menuSelect = document.getElementById("viewing-as-select");
  if (menuSelect && menuSelect.value !== personId) menuSelect.value = personId;
}

// ═══════════════════════════════════════════════════════════════
// Photo Gallery — Faceted Search
// ═══════════════════════════════════════════════════════════════

let _galleryFiltersInited = false;

// Active facet selections: { year: Set, place: Set, person: Set, status: Set, exif: Set }
export const GALLERY_FILTERS = { year: new Set(), place: new Set(), person: new Set(), status: new Set(), exif: new Set() };

// Text search + date range filter state
let GALLERY_TEXT_SEARCH = "";
let GALLERY_YEAR_FROM = null;
let GALLERY_YEAR_TO = null;

export function syncGalleryFilterUrl() {
  router.navigate("/photos", { replace: true, query: currentGalleryFilterQuery() });
}

export function toggleGalleryFilter(facet, value) {
  const set = GALLERY_FILTERS[facet];
  if (set.has(value)) set.delete(value);
  else set.add(value);
  renderPhotoGallery();
  renderGalleryFacets();
  renderActiveFilterPills();
  syncGalleryFilterUrl();
}

export function clearGalleryFilter(facet) {
  GALLERY_FILTERS[facet].clear();
  renderPhotoGallery();
  renderGalleryFacets();
  renderActiveFilterPills();
  syncGalleryFilterUrl();
}

export function clearAllGalleryFilters() {
  for (const k in GALLERY_FILTERS) GALLERY_FILTERS[k].clear();
  GALLERY_TEXT_SEARCH = "";
  GALLERY_YEAR_FROM = null;
  GALLERY_YEAR_TO = null;
  const textEl = document.getElementById("gallery-text-search");
  if (textEl) textEl.value = "";
  const fromEl = document.getElementById("gallery-year-from");
  if (fromEl) fromEl.value = "";
  const toEl = document.getElementById("gallery-year-to");
  if (toEl) toEl.value = "";
  renderPhotoGallery();
  renderGalleryFacets();
  renderActiveFilterPills();
}

export function getFilteredPhotos() {
  if (!S.DATA.photos) return [];
  const { year, place, person, status, exif } = GALLERY_FILTERS;

  return S.DATA.photos.filter(photo => {
    // Year filter
    if (year.size > 0) {
      const photoYear = photo.date ? photo.date.substring(0, 4) : null;
      if (!photoYear || !year.has(photoYear)) return false;
    }

    // Place filter
    if (place.size > 0) {
      if (!photo.place || !place.has(photo.place)) return false;
    }

    // Person filter
    if (person.size > 0) {
      const tagged = (photo.tagged_people || []).map(tp => tp.person_id);
      if (!tagged.some(id => person.has(id))) return false;
    }

    // Status filter
    if (status.size > 0) {
      const isTagged = (photo.tagged_people || []).length > 0;
      const hasDate = !!photo.date;
      const hasPlace = !!photo.place;
      if (status.has("untagged") && isTagged) return false;
      if (status.has("tagged") && !isTagged) return false;
      if (status.has("no-date") && hasDate) return false;
      if (status.has("no-place") && hasPlace) return false;
      // Multiple status filters: AND logic — photo must match all
      if (status.has("has-date") && !hasDate) return false;
      if (status.has("has-place") && !hasPlace) return false;
    }

    // EXIF filter
    if (exif.size > 0) {
      const hasGps = photo.lat != null && photo.lng != null;
      if (exif.has("has-gps") && !hasGps) return false;
      if (exif.has("no-gps") && hasGps) return false;
      if (exif.has("has-date") && !photo.date) return false;
      if (exif.has("no-date") && photo.date) return false;
    }

    // Text search filter
    if (GALLERY_TEXT_SEARCH) {
      const q = GALLERY_TEXT_SEARCH.toLowerCase();
      const placeMatch = (photo.place || "").toLowerCase().includes(q);
      const peopleMatch = (photo.tagged_people || []).some(tp => {
        const p = S.PEOPLE_MAP[tp.person_id];
        if (!p) return false;
        const nameMatch = (p.given_name || "").toLowerCase().includes(q) ||
                          (p.surname || "").toLowerCase().includes(q) ||
                          (p.fullName || "").toLowerCase().includes(q);
        const captionMatch = (tp.caption || "").toLowerCase().includes(q);
        return nameMatch || captionMatch;
      });
      if (!placeMatch && !peopleMatch) return false;
    }

    // Date range filter
    if (GALLERY_YEAR_FROM !== null || GALLERY_YEAR_TO !== null) {
      if (!photo.date) return false;
      const photoYear = parseInt(photo.date.substring(0, 4));
      if (isNaN(photoYear)) return false;
      if (GALLERY_YEAR_FROM !== null && photoYear < GALLERY_YEAR_FROM) return false;
      if (GALLERY_YEAR_TO !== null && photoYear > GALLERY_YEAR_TO) return false;
    }

    return true;
  });
}

export function computeFacetCounts(photos) {
  const counts = {
    years: {},
    places: {},
    people: {},
    status: { tagged: 0, untagged: 0, "has-date": 0, "no-date": 0, "has-place": 0, "no-place": 0 },
    exif: { "has-gps": 0, "no-gps": 0, "has-date": 0, "no-date": 0 },
  };

  for (const photo of photos) {
    // Years
    if (photo.date) {
      const y = photo.date.substring(0, 4);
      counts.years[y] = (counts.years[y] || 0) + 1;
    }

    // Places
    if (photo.place) {
      counts.places[photo.place] = (counts.places[photo.place] || 0) + 1;
    }

    // People
    for (const tp of photo.tagged_people || []) {
      counts.people[tp.person_id] = (counts.people[tp.person_id] || 0) + 1;
    }

    // Status
    const isTagged = (photo.tagged_people || []).length > 0;
    counts.status[isTagged ? "tagged" : "untagged"]++;
    counts.status[photo.date ? "has-date" : "no-date"]++;
    counts.status[photo.place ? "has-place" : "no-place"]++;

    // EXIF
    const hasGps = photo.lat != null && photo.lng != null;
    counts.exif[hasGps ? "has-gps" : "no-gps"]++;
    counts.exif[photo.date ? "has-date" : "no-date"]++;
  }

  return counts;
}

export function renderFacetOption(facet, value, label, count, total) {
  const active = GALLERY_FILTERS[facet].has(value);
  const pct = total > 0 ? Math.round(count / total * 100) : 0;
  return `<button class="facet-option ${active ? "active" : ""}" onclick="toggleGalleryFilter('${facet}', '${value.replace(/'/g, "\\'")}')">
    <span class="facet-option-label">${label}</span>
    <span class="facet-option-meta"><span class="facet-option-count">${count}</span><span class="facet-option-bar"><span style="width:${pct}%"></span></span></span>
  </button>`;
}

export function renderGalleryFacets() {
  const allPhotos = S.DATA.photos || [];
  const total = allPhotos.length;
  // Compute counts on the full dataset (not filtered) so users see total distribution
  const counts = computeFacetCounts(allPhotos);

  // Status facet
  const statusEl = document.getElementById("facet-status-options");
  if (statusEl) {
    const statusLabels = {
      "untagged": "Untagged", "tagged": "Tagged",
      "no-date": "No date", "has-date": "Has date",
      "no-place": "No place", "has-place": "Has place",
    };
    statusEl.innerHTML = Object.entries(statusLabels)
      .filter(([k]) => counts.status[k] > 0)
      .map(([k, label]) => renderFacetOption("status", k, label, counts.status[k], total))
      .join("");
  }

  // Years facet — sorted descending
  const yearsEl = document.getElementById("facet-year-options");
  if (yearsEl) {
    const years = Object.entries(counts.years).sort((a, b) => b[0].localeCompare(a[0]));
    yearsEl.innerHTML = years
      .map(([y, c]) => renderFacetOption("year", y, y, c, total))
      .join("");
  }

  // Places facet — sorted by count desc
  const placesEl = document.getElementById("facet-place-options");
  if (placesEl) {
    const places = Object.entries(counts.places).sort((a, b) => b[1] - a[1]);
    placesEl.innerHTML = places
      .map(([p, c]) => renderFacetOption("place", p, escapeHtml(p), c, total))
      .join("");
  }

  // People facet — sorted by count desc, filtered by search
  const peopleEl = document.getElementById("facet-people-options");
  const searchEl = document.getElementById("facet-people-search");
  if (peopleEl) {
    const searchTerm = (searchEl?.value || "").toLowerCase();
    const people = Object.entries(counts.people)
      .map(([id, c]) => ({ id, name: S.PEOPLE_MAP[id]?.fullName || id, count: c }))
      .filter(p => !searchTerm || p.name.toLowerCase().includes(searchTerm))
      .sort((a, b) => b.count - a.count);
    peopleEl.innerHTML = people
      .map(p => renderFacetOption("person", p.id, personThumb(p.id, 18) + ` <span>${escapeHtml(p.name)}</span>`, p.count, total))
      .join("");
  }

  // EXIF facet
  const exifEl = document.getElementById("facet-exif-options");
  if (exifEl) {
    const exifLabels = {
      "has-gps": "Has GPS", "no-gps": "No GPS",
      "has-date": "Has EXIF date", "no-date": "No EXIF date",
    };
    exifEl.innerHTML = Object.entries(exifLabels)
      .filter(([k]) => counts.exif[k] > 0)
      .map(([k, label]) => renderFacetOption("exif", k, label, counts.exif[k], total))
      .join("");
  }
}

export function renderActiveFilterPills() {
  const container = document.getElementById("photos-active-filters");
  if (!container) return;

  const pills = [];
  const labels = {
    year: "Year", place: "Place", person: "Person", status: "Status", exif: "EXIF",
  };
  const valueFmt = {
    person: (v) => S.PEOPLE_MAP[v]?.fullName || v,
    status: (v) => ({ untagged: "Untagged", tagged: "Tagged", "no-date": "No date", "has-date": "Has date", "no-place": "No place", "has-place": "Has place" }[v] || v),
    exif: (v) => ({ "has-gps": "Has GPS", "no-gps": "No GPS", "has-date": "Has EXIF date", "no-date": "No EXIF date" }[v] || v),
  };

  for (const [facet, set] of Object.entries(GALLERY_FILTERS)) {
    for (const value of set) {
      const display = valueFmt[facet] ? valueFmt[facet](value) : value;
      pills.push(`<span class="filter-pill" onclick="toggleGalleryFilter('${facet}', '${value.replace(/'/g, "\\'")}')">${labels[facet]}: ${escapeHtml(display)} <span class="filter-pill-x">&times;</span></span>`);
    }
  }

  // Text search pill
  if (GALLERY_TEXT_SEARCH) {
    pills.push(`<span class="filter-pill" onclick="clearGalleryTextSearch()">Search: "${escapeHtml(GALLERY_TEXT_SEARCH)}" <span class="filter-pill-x">&times;</span></span>`);
  }

  // Date range pill
  if (GALLERY_YEAR_FROM !== null || GALLERY_YEAR_TO !== null) {
    const rangeLabel = GALLERY_YEAR_FROM && GALLERY_YEAR_TO
      ? `${GALLERY_YEAR_FROM}\u2013${GALLERY_YEAR_TO}`
      : GALLERY_YEAR_FROM ? `${GALLERY_YEAR_FROM}+` : `\u2013${GALLERY_YEAR_TO}`;
    pills.push(`<span class="filter-pill" onclick="clearGalleryDateRange()">Years: ${rangeLabel} <span class="filter-pill-x">&times;</span></span>`);
  }

  if (pills.length > 0) {
    pills.push(`<button class="filter-clear-all" onclick="clearAllGalleryFilters()">Clear all</button>`);
  }

  container.innerHTML = pills.join("");
}

export function clearGalleryTextSearch() {
  GALLERY_TEXT_SEARCH = "";
  const el = document.getElementById("gallery-text-search");
  if (el) el.value = "";
  renderPhotoGallery();
  renderGalleryFacets();
  renderActiveFilterPills();
}

export function clearGalleryDateRange() {
  GALLERY_YEAR_FROM = null;
  GALLERY_YEAR_TO = null;
  const fromEl = document.getElementById("gallery-year-from");
  const toEl = document.getElementById("gallery-year-to");
  if (fromEl) fromEl.value = "";
  if (toEl) toEl.value = "";
  renderPhotoGallery();
  renderGalleryFacets();
  renderActiveFilterPills();
}

export function renderPhotoGallery() {
  const grid = document.getElementById("photos-grid");
  const badge = document.getElementById("photos-count-badge");
  if (!grid) return;

  const isEditor = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  const filtered = getFilteredPhotos();
  const total = S.DATA.photos ? S.DATA.photos.length : 0;

  if (badge) {
    badge.textContent = filtered.length === total ? `${total}` : `${filtered.length} / ${total}`;
  }

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="photos-empty">${total === 0 ? "No photos uploaded yet" : "No photos match the current filters"}</div>`;
    return;
  }

  // Sort: most recent first, undated at end
  const sorted = [...filtered].sort((a, b) => {
    if (!a.date && !b.date) return 0;
    if (!a.date) return 1;
    if (!b.date) return -1;
    return b.date.localeCompare(a.date);
  });

  grid.innerHTML = sorted.map(photo => {
    const tagCount = (photo.tagged_people || []).length;
    const hasGps = photo.lat != null && photo.lng != null;
    const esc = escapeHtml;
    const selected = GALLERY_SELECT_MODE && GALLERY_SELECTED.has(photo.file_path);
    return `<div class="photos-grid-item${selected ? " gallery-selected" : ""}" data-photo-path="${photo.file_path}" data-photo-id="${photo.id}">
      ${GALLERY_SELECT_MODE ? `<div class="gallery-select-check${selected ? " checked" : ""}" onclick="togglePhotoSelection('${photo.file_path}')">${selected ? "&#10003;" : ""}</div>` : ""}
      <div class="photos-grid-img" onclick="galleryPhotoClick(event, '${photo.file_path}', ${photo.id})">
        <img src="/${photo.file_path}" alt="" loading="lazy" />
        ${tagCount > 0 ? `<span class="photos-grid-tag-count">${tagCount} tagged</span>` : `<span class="photos-grid-untagged">Untagged</span>`}
        ${hasGps ? `<span class="photos-grid-gps" title="Has GPS coordinates">&#128205;</span>` : ""}
      </div>
      <div class="photos-grid-info">
        <div class="photos-grid-info-text">
          ${photo.date ? `<span class="photo-date">${photo.date_circa ? "c. " : ""}${esc(photo.date)}</span>` : ""}
          ${photo.place ? `<span class="photo-place" title="${esc(photo.place)}">${esc(photo.place)}</span>` : ""}
          ${!photo.date && !photo.place ? `<span class="photo-place photo-no-meta">No metadata</span>` : ""}
        </div>
        ${isEditor ? `<button class="photos-grid-edit-btn" onclick="event.stopPropagation(); toggleGalleryEdit('${photo.file_path}')" title="Edit metadata">&#9998;</button>` : ""}
      </div>
      <div class="gallery-edit-form hidden" id="gallery-edit-${photo.id}"></div>
    </div>`;
  }).join("");

  // Fade-in (P2): flip .is-loaded once each grid image is ready (or already
  // cached). Pairs with the .js-fade CSS rule that starts these imgs at opacity 0.
  grid.querySelectorAll(".photos-grid-img img").forEach((img) => {
    if (img.complete && img.naturalWidth) {
      img.classList.add("is-loaded");
    } else {
      const flip = () => img.classList.add("is-loaded");
      img.addEventListener("load", flip, { once: true });
      img.addEventListener("error", flip, { once: true });
    }
  });

  if (GALLERY_SELECT_MODE) renderBulkToolbar();
}

// ── Gallery select mode & quick year picker ───────────────────

let GALLERY_SELECT_MODE = false;
export const GALLERY_SELECTED = new Set();

export function galleryPhotoClick(event, filePath, photoId) {
  if (GALLERY_SELECT_MODE) {
    togglePhotoSelection(filePath);
    return;
  }
  const isEditor = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  const photo = S.DATA.photos?.find(p => p.file_path === filePath);
  if (photo && !photo.date && isEditor) {
    showQuickYearPicker(photo, event.currentTarget);
    return;
  }
  const filtered = getFilteredPhotos();
  const sorted = [...filtered].sort((a, b) => {
    if (!a.date && !b.date) return 0;
    if (!a.date) return 1;
    if (!b.date) return -1;
    return b.date.localeCompare(a.date);
  });
  const galleryPaths = sorted.map(p => p.file_path);
  openLightbox("/" + filePath, "", filePath, galleryPaths);
  router.navigate(`/photos/view/${filePath}`);
}

export function toggleSelectMode() {
  GALLERY_SELECT_MODE = !GALLERY_SELECT_MODE;
  GALLERY_SELECTED.clear();
  const btn = document.getElementById("gallery-select-btn");
  if (btn) btn.textContent = GALLERY_SELECT_MODE ? "Cancel" : "Select";
  removeBulkToolbar();
  renderPhotoGallery();
}

export function togglePhotoSelection(filePath) {
  if (GALLERY_SELECTED.has(filePath)) GALLERY_SELECTED.delete(filePath);
  else GALLERY_SELECTED.add(filePath);
  renderPhotoGallery();
}

export function renderBulkToolbar() {
  removeBulkToolbar();
  if (GALLERY_SELECTED.size === 0) return;
  const bar = document.createElement("div");
  bar.id = "gallery-bulk-toolbar";
  bar.className = "gallery-bulk-toolbar";
  bar.innerHTML = `
    <span class="bulk-count">${GALLERY_SELECTED.size} selected</span>
    <input type="number" id="bulk-year-input" class="gallery-year-input" placeholder="Year" min="1600" max="2099" />
    <button class="bulk-set-btn" onclick="bulkAssignYear()">Set Year</button>
    <button class="bulk-cancel-btn" onclick="toggleSelectMode()">Cancel</button>
  `;
  document.body.appendChild(bar);
}

export function removeBulkToolbar() {
  const existing = document.getElementById("gallery-bulk-toolbar");
  if (existing) existing.remove();
}

export async function bulkAssignYear() {
  const yearInput = document.getElementById("bulk-year-input");
  const year = yearInput?.value?.trim();
  if (!year || isNaN(parseInt(year))) {
    showToast("Enter a valid year", "error");
    return;
  }
  const photoIds = [];
  for (const fp of GALLERY_SELECTED) {
    const photo = S.DATA.photos?.find(p => p.file_path === fp);
    if (photo) photoIds.push(photo.id);
  }
  if (photoIds.length === 0) return;

  try {
    const res = await fetch("/api/photos/bulk-metadata", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo_ids: photoIds, date: year, date_circa: true }),
    });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    const result = await res.json();
    // Update local data
    for (const id of result.updated) {
      const photo = S.DATA.photos?.find(p => p.id === id);
      if (photo) {
        photo.date = year;
        photo.date_circa = true;
      }
    }
    showToast(`Updated ${result.updated.length} photos`);
    toggleSelectMode();
  } catch (err) {
    showToast("Bulk update failed: " + err.message, "error");
  }
}

export function showQuickYearPicker(photo, anchorEl) {
  // Remove any existing picker
  const existing = document.getElementById("quick-year-picker");
  if (existing) existing.remove();

  const rect = anchorEl.getBoundingClientRect();
  const picker = document.createElement("div");
  picker.id = "quick-year-picker";
  picker.className = "quick-year-picker";
  picker.style.top = `${rect.bottom + window.scrollY + 4}px`;
  picker.style.left = `${rect.left + window.scrollX}px`;
  picker.innerHTML = `
    <div class="qyp-header">Set approximate year</div>
    <div class="qyp-body">
      <input type="number" id="qyp-year" class="gallery-year-input" placeholder="e.g. 1985" min="1600" max="2099" autofocus />
      <button class="qyp-save" onclick="saveQuickYear(${photo.id})">Save</button>
    </div>
    <a href="javascript:void(0)" class="qyp-skip" onclick="document.getElementById('quick-year-picker').remove(); openLightbox('/${photo.file_path}', '', '${photo.file_path}')">View photo instead</a>
  `;
  document.body.appendChild(picker);

  // Close on outside click
  setTimeout(() => {
    document.addEventListener("click", function _qypClose(e) {
      if (!picker.contains(e.target)) {
        picker.remove();
        document.removeEventListener("click", _qypClose);
      }
    });
  }, 0);

  // Save on Enter
  const input = picker.querySelector("#qyp-year");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveQuickYear(photo.id);
    if (e.key === "Escape") picker.remove();
  });
}

export async function saveQuickYear(photoId) {
  const input = document.getElementById("qyp-year");
  const year = input?.value?.trim();
  if (!year || isNaN(parseInt(year))) {
    showToast("Enter a valid year", "error");
    return;
  }
  try {
    const res = await fetch(`/api/photos/${photoId}/metadata`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: year, date_circa: true }),
    });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    const photo = S.DATA.photos?.find(p => p.id === photoId);
    if (photo) {
      photo.date = year;
      photo.date_circa = true;
    }
    document.getElementById("quick-year-picker")?.remove();
    showToast(`Year set to c. ${year}`);
    renderPhotoGallery();
    renderGalleryFacets();
  } catch (err) {
    showToast("Could not save year: " + err.message, "error");
  }
}

// ── Gallery photo upload (Photos tab) ──────────────────────────
export function initGalleryUpload() {
  const btn = document.getElementById("gallery-upload-btn");
  const fileInput = document.getElementById("gallery-file-input");
  const dropZone = document.getElementById("gallery-drop-zone");
  if (!btn || !fileInput) return;

  btn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    await _galleryUploadFiles(fileInput.files);
    fileInput.value = "";
  });

  // Wire drop zone on the photos grid area
  const grid = document.getElementById("photos-grid");
  if (grid) {
    grid.addEventListener("dragover", (e) => { e.preventDefault(); grid.classList.add("drag-over"); });
    grid.addEventListener("dragleave", () => grid.classList.remove("drag-over"));
    grid.addEventListener("drop", async (e) => {
      e.preventDefault();
      grid.classList.remove("drag-over");
      const files = [...e.dataTransfer.files].filter(f => f.type.startsWith("image/"));
      if (files.length > 0) await _galleryUploadFiles(files);
    });
  }
}

export async function _galleryUploadFiles(files) {
  if (!files || files.length === 0) return;

  const progressEl = document.getElementById("gallery-upload-progress");
  const progressText = document.getElementById("gallery-upload-text");
  if (progressEl) progressEl.classList.remove("hidden");

  let uploaded = 0;
  const total = files.length;
  const errors = [];

  for (let i = 0; i < total; i++) {
    let file = files[i];
    if (progressText) progressText.textContent = `Uploading ${i + 1} of ${total}: ${file.name}`;

    file = await resizeImageFile(file);

    const formData = new FormData();
    formData.append("photo", file);

    try {
      const resp = await fetch("/api/photos/upload", { method: "POST", body: formData });
      const data = await resp.json().catch(() => ({}));

      if (resp.ok && data.path) {
        uploaded++;
      } else {
        errors.push(`${file.name}: ${data.error || "upload failed"}`);
      }
    } catch (err) {
      errors.push(`${file.name}: ${err.message}`);
    }
  }

  if (progressEl) progressEl.classList.add("hidden");

  if (uploaded > 0) {
    showToast(`${uploaded} photo${uploaded > 1 ? "s" : ""} uploaded`);
    // Reload full data to pick up new photos
    const resp = await fetch("/api/data");
    if (resp.ok) {
      const newData = await resp.json();
      S.DATA.photos = newData.photos;
      S.PHOTOS_MAP = {};
      for (const photo of S.DATA.photos) {
        S.PHOTOS_MAP[photo.file_path] = photo;
      }
      S.ALL_PHOTOS = S.DATA.photos.map(p => p.file_path);
      renderPhotoGallery();
      renderGalleryFacets();
    }
  }
  if (errors.length > 0) {
    const msg = errors.length === 1
      ? errors[0]
      : `${errors.length} of ${total} uploads failed — ${errors[0]}`;
    showToast(msg, "error");
    console.warn("Gallery upload errors:", errors);
  }
}

export function toggleGalleryEdit(photoPath) {
  const photoData = S.PHOTOS_MAP[photoPath];
  if (!photoData) return;

  const formId = `gallery-edit-${photoData.id}`;
  const form = document.getElementById(formId);
  if (!form) return;

  // Toggle visibility
  if (!form.classList.contains("hidden")) {
    form.classList.add("hidden");
    form.innerHTML = "";
    return;
  }

  // Close any other open edit forms
  document.querySelectorAll(".gallery-edit-form:not(.hidden)").forEach(f => {
    f.classList.add("hidden");
    f.innerHTML = "";
  });

  const esc = escapeHtml;
  const date = photoData.date || "";
  const circa = photoData.date_circa ? "checked" : "";
  const place = photoData.place || "";
  const lat = photoData.lat != null ? photoData.lat : "";
  const lng = photoData.lng != null ? photoData.lng : "";
  const ptype = photoData.photo_type || "photo";

  form.innerHTML = `
    <div class="ge-row">
      <div class="ge-field">
        <label>Date</label>
        <div class="ge-date-row">
          <input type="text" class="ge-input" data-gf="date" value="${esc(date)}" placeholder="YYYY-MM-DD" />
          <label class="ge-circa"><input type="checkbox" data-gf="date_circa" ${circa} /> ~circa</label>
        </div>
      </div>
    </div>
    <div class="ge-row">
      <div class="ge-field">
        <label>Place</label>
        <input type="text" class="ge-input" data-gf="place" value="${esc(place)}" placeholder="Location" />
      </div>
    </div>
    <div class="ge-row ge-row-pair">
      <div class="ge-field">
        <label>Lat</label>
        <input type="text" class="ge-input ge-coord" data-gf="lat" value="${lat}" placeholder="40.7128" />
      </div>
      <div class="ge-field">
        <label>Lng</label>
        <input type="text" class="ge-input ge-coord" data-gf="lng" value="${lng}" placeholder="-74.0060" />
      </div>
      <div class="ge-field">
        <label>Type</label>
        <select class="ge-input" data-gf="photo_type">
          ${["photo","portrait","group","document","headstone"].map(t => `<option value="${t}" ${ptype === t ? "selected" : ""}>${t[0].toUpperCase() + t.slice(1)}</option>`).join("")}
        </select>
      </div>
    </div>
    <div class="ge-row ge-row-tags">
      <label>Tagged</label>
      <div class="ge-tags">${_buildGalleryTagChips(photoPath)}</div>
    </div>
    <div class="ge-status" id="ge-status-${photoData.id}"></div>
  `;

  form.classList.remove("hidden");

  // Wire autosave on all inputs
  const saveGalleryMeta = async () => {
    const fields = {};
    fields.date = form.querySelector('[data-gf="date"]')?.value.trim() || null;
    fields.date_circa = form.querySelector('[data-gf="date_circa"]')?.checked || false;
    fields.place = form.querySelector('[data-gf="place"]')?.value.trim() || null;
    fields.photo_type = form.querySelector('[data-gf="photo_type"]')?.value || "photo";
    const latVal = form.querySelector('[data-gf="lat"]')?.value.trim();
    const lngVal = form.querySelector('[data-gf="lng"]')?.value.trim();
    fields.lat = latVal ? parseFloat(latVal) : null;
    fields.lng = lngVal ? parseFloat(lngVal) : null;

    const statusEl = document.getElementById(`ge-status-${photoData.id}`);
    try {
      const resp = await fetch(`/api/photos/${photoData.id}/metadata`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (resp.ok) {
        const updated = await resp.json();
        Object.assign(photoData, updated);
        if (statusEl) { statusEl.textContent = "Saved"; statusEl.className = "ge-status ge-saved"; }
        // Update the info text above the form
        const item = form.closest(".photos-grid-item");
        if (item) {
          const infoText = item.querySelector(".photos-grid-info-text");
          if (infoText) {
            const d = updated.date;
            const p = updated.place;
            infoText.innerHTML = `${d ? `<span class="photo-date">${updated.date_circa ? "c. " : ""}${escapeHtml(d)}</span>` : ""}${p ? `<span class="photo-place" title="${escapeHtml(p)}">${escapeHtml(p)}</span>` : ""}${!d && !p ? `<span class="photo-place photo-no-meta">No metadata</span>` : ""}`;
          }
          // Update GPS badge
          const imgDiv = item.querySelector(".photos-grid-img");
          const existingGps = imgDiv?.querySelector(".photos-grid-gps");
          if (updated.lat != null && updated.lng != null) {
            if (!existingGps) {
              imgDiv.insertAdjacentHTML("beforeend", `<span class="photos-grid-gps" title="Has GPS coordinates">&#128205;</span>`);
            }
          } else if (existingGps) {
            existingGps.remove();
          }
        }
        renderGalleryFacets();
      } else {
        const err = await resp.json().catch(() => ({}));
        if (statusEl) { statusEl.textContent = err.error || "Error"; statusEl.className = "ge-status ge-error"; }
      }
    } catch (err) {
      if (statusEl) { statusEl.textContent = err.message; statusEl.className = "ge-status ge-error"; }
    }
  };

  form.querySelectorAll("input[type=text], select").forEach(el => {
    el.addEventListener("blur", saveGalleryMeta);
    el.addEventListener("change", saveGalleryMeta);
    el.addEventListener("click", e => e.stopPropagation());
  });
  form.querySelectorAll("input[type=checkbox]").forEach(el => {
    el.addEventListener("change", saveGalleryMeta);
    el.addEventListener("click", e => e.stopPropagation());
  });

  // Wire tag add button
  _wireGalleryTagEvents(form, photoPath);
}

export function _buildGalleryTagChips(photoPath) {
  const photoData = S.PHOTOS_MAP[photoPath];
  if (!photoData) return "";
  const people = photoData.tagged_people || [];
  let chips = people.map(tp => {
    const name = [tp.given_name, tp.surname].filter(Boolean).join(" ") || tp.person_id;
    return `<span class="ge-tag-chip">${personThumb(tp.person_id, 16)} ${name} <span class="ge-tag-remove" data-person="${tp.person_id}" data-photo-path="${photoPath}">&times;</span></span>`;
  }).join("");
  return `${chips}<button class="ge-tag-add" data-photo-path="${photoPath}">+ Tag</button>`;
}

export function _wireGalleryTagEvents(form, photoPath) {
  const photoData = S.PHOTOS_MAP[photoPath];
  if (!photoData) return;

  // Remove tag
  form.querySelectorAll(".ge-tag-remove").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const personId = btn.dataset.person;
      try {
        const resp = await fetch(`/api/photos/${photoData.id}/tag/${personId}`, { method: "DELETE" });
        if (resp.ok) {
          photoData.tagged_people = (photoData.tagged_people || []).filter(tp => tp.person_id !== personId);
          const tagsDiv = btn.closest(".ge-tags");
          if (tagsDiv) { tagsDiv.innerHTML = _buildGalleryTagChips(photoPath); _wireGalleryTagEvents(form, photoPath); }
          // Update tag count badge
          const item = form.closest(".photos-grid-item");
          const countBadge = item?.querySelector(".photos-grid-tag-count, .photos-grid-untagged");
          if (countBadge) {
            const ct = (photoData.tagged_people || []).length;
            countBadge.className = ct > 0 ? "photos-grid-tag-count" : "photos-grid-untagged";
            countBadge.textContent = ct > 0 ? `${ct} tagged` : "Untagged";
          }
          renderGalleryFacets();
        }
      } catch (err) { showToast("Could not remove tag: " + err.message, "error"); }
    });
  });

  // Add tag
  form.querySelectorAll(".ge-tag-add").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      // Remove any existing search
      form.querySelectorAll(".ge-tag-search-wrap").forEach(el => el.remove());

      const wrap = document.createElement("div");
      wrap.className = "ge-tag-search-wrap";
      const input = document.createElement("input");
      input.type = "text";
      input.className = "ge-tag-search-input";
      input.placeholder = "Search people...";
      const results = document.createElement("div");
      results.className = "ge-tag-search-results";
      wrap.appendChild(input);
      wrap.appendChild(results);
      btn.parentElement.appendChild(wrap);
      input.focus();

      const alreadyTagged = new Set((photoData.tagged_people || []).map(tp => tp.person_id));

      input.addEventListener("input", () => {
        const q = input.value.toLowerCase().trim();
        if (!q) { results.innerHTML = ""; return; }
        const matches = Object.values(S.PEOPLE_MAP)
          .filter(p => !alreadyTagged.has(p.id) && p.fullName.toLowerCase().includes(q))
          .slice(0, 6);
        results.innerHTML = matches.map(p =>
          `<div class="ge-tag-search-result" data-id="${p.id}">${personThumb(p.id, 18)} ${p.fullName}</div>`
        ).join("");
        results.querySelectorAll(".ge-tag-search-result").forEach(el => {
          el.addEventListener("click", async (ev) => {
            ev.stopPropagation();
            const tagId = el.dataset.id;
            try {
              const resp = await fetch(`/api/photos/${photoData.id}/tag`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ person_id: tagId }),
              });
              if (resp.ok) {
                const person = S.PEOPLE_MAP[tagId];
                photoData.tagged_people = [...(photoData.tagged_people || []), {
                  person_id: tagId,
                  given_name: person?.given_name || "",
                  surname: person?.surname || "",
                  is_profile: false, caption: "",
                }];
                const tagsDiv = btn.closest(".ge-tags");
                if (tagsDiv) { tagsDiv.innerHTML = _buildGalleryTagChips(photoPath); _wireGalleryTagEvents(form, photoPath); }
                // Update tag count badge
                const item = form.closest(".photos-grid-item");
                const countBadge = item?.querySelector(".photos-grid-tag-count, .photos-grid-untagged");
                if (countBadge) {
                  const ct = (photoData.tagged_people || []).length;
                  countBadge.className = "photos-grid-tag-count";
                  countBadge.textContent = `${ct} tagged`;
                }
                renderGalleryFacets();
              }
            } catch (err) { showToast("Could not tag: " + err.message, "error"); }
          });
        });
      });

      input.addEventListener("click", e => e.stopPropagation());
      // Close on Escape
      input.addEventListener("keydown", e => { if (e.key === "Escape") wrap.remove(); });
    });
  });
}

export function initPhotoGalleryFilters() {
  if (_galleryFiltersInited) return;
  _galleryFiltersInited = true;

  renderGalleryFacets();
  renderActiveFilterPills();

  // Wire people search filter
  const searchEl = document.getElementById("facet-people-search");
  if (searchEl) {
    let t = null;
    searchEl.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(renderGalleryFacets, 150);
    });
  }

  // Wire gallery text search
  const textSearchEl = document.getElementById("gallery-text-search");
  if (textSearchEl) {
    let ts = null;
    textSearchEl.addEventListener("input", () => {
      clearTimeout(ts);
      ts = setTimeout(() => {
        GALLERY_TEXT_SEARCH = textSearchEl.value.trim();
        renderPhotoGallery();
        renderGalleryFacets();
        renderActiveFilterPills();
      }, 200);
    });
  }

  // Wire gallery date range inputs
  const yearFromEl = document.getElementById("gallery-year-from");
  const yearToEl = document.getElementById("gallery-year-to");
  if (yearFromEl) {
    yearFromEl.addEventListener("change", () => {
      GALLERY_YEAR_FROM = yearFromEl.value ? parseInt(yearFromEl.value) : null;
      renderPhotoGallery();
      renderGalleryFacets();
      renderActiveFilterPills();
    });
  }
  if (yearToEl) {
    yearToEl.addEventListener("change", () => {
      GALLERY_YEAR_TO = yearToEl.value ? parseInt(yearToEl.value) : null;
      renderPhotoGallery();
      renderGalleryFacets();
      renderActiveFilterPills();
    });
  }
}

export function refreshAllViews() {
  updateStats();
  renderTree();
  renderTimeline(document.getElementById("timeline-filter")?.value || "all");
  // Pre-fill relationship calculator with current viewer
  prefillRelationshipCalculator();
  // Re-render map if it was already initialized
  if (S.MAP) renderMap();
  // Re-render photo gallery
  renderPhotoGallery();
}

export function prefillRelationshipCalculator() {
  if (!S.CENTER_ID_A) return;
  const pickerA = document.getElementById("picker-a");
  if (!pickerA) return;
  const inputA = pickerA.querySelector(".picker-search");
  if (!inputA) return;
  const person = S.PEOPLE_MAP[S.CENTER_ID_A];
  if (!person) return;
  pickerA._selectedId = S.CENTER_ID_A;
  inputA.value = person.fullName;
  inputA.dataset.locked = person.fullName;
  computeRelationship();
}

export function updateDynamicHeader(centerA, centerB) {
  const titleEl = document.getElementById("family-title");
  const subtitleEl = document.getElementById("family-subtitle");
  if (!titleEl) return;

  const personA = S.PEOPLE_MAP[centerA];
  const personB = centerB && centerB !== centerA ? S.PEOPLE_MAP[centerB] : null;

  // Build title from surnames
  const surnameA = personA?.surname || "";
  const surnameB = personB?.surname || "";

  if (surnameA && surnameB && surnameA !== surnameB) {
    titleEl.textContent = `The ${surnameA} & ${surnameB} Family`;
  } else if (surnameA) {
    titleEl.textContent = `The ${surnameA} Family`;
  }

  // Subtitle: "Viewing as [Name]"
  if (subtitleEl && personA) {
    const name = `${personA.given_name || ""} ${personA.surname || ""}`.trim();
    subtitleEl.textContent = `Viewing as ${name}`;
    subtitleEl.style.display = "";
  }
}

export function applyAuth() {
  const loggedIn = document.getElementById("auth-logged-in");
  const loggedOut = document.getElementById("auth-logged-out");
  if (!loggedIn || !loggedOut) return;

  if (S.AUTH_USER) {
    loggedIn.style.display = "";
    loggedOut.style.display = "none";

    // Populate user pill
    const pillName = document.getElementById("user-pill-name");
    const pillPhoto = document.getElementById("user-pill-photo");
    const menuName = document.getElementById("user-menu-name");
    const menuEmail = document.getElementById("user-menu-email");
    const menuPhoto = document.getElementById("user-menu-photo");

    const firstName = (S.AUTH_USER.name || "").split(" ")[0];
    pillName.textContent = firstName;

    const picUrl = S.AUTH_USER.picture || "";
    if (picUrl) {
      pillPhoto.src = picUrl;
      pillPhoto.alt = S.AUTH_USER.name;
      pillPhoto.style.display = "";
      menuPhoto.src = picUrl;
      menuPhoto.alt = S.AUTH_USER.name;
      menuPhoto.style.display = "";
    } else {
      pillPhoto.style.display = "none";
      menuPhoto.style.display = "none";
    }

    menuName.textContent = S.AUTH_USER.name || "";
    menuEmail.textContent = S.AUTH_USER.email || "";

    // Role badge for non-family editors
    const roleBadge = document.getElementById("user-menu-role-badge");
    if (roleBadge) {
      const role = S.AUTH_USER.role;
      if (role && role !== "editor" && S.AUTH_USER.person_id?.startsWith("editor:")) {
        roleBadge.textContent = role.charAt(0).toUpperCase() + role.slice(1);
        roleBadge.className = `user-menu-role-badge role-${role}`;
        roleBadge.style.display = "";
      } else {
        roleBadge.style.display = "none";
      }
    }

    // Show "Manage Editors" for admins
    const manageBtn = document.getElementById("manage-editors-btn");
    if (manageBtn) {
      const isAdmin = S.AUTH_USER.role === "owner" ||
        S.AUTH_USER.person_id === S.CONFIG?.adminPersonId;
      manageBtn.style.display = (S.AUTH_USER.is_editor && isAdmin) ? "" : "none";
    }
  } else {
    loggedIn.style.display = "none";
    loggedOut.style.display = "";
    // Re-try rendering the Google button in case the SDK finished loading
    // after checkAuth() resolved, or in case we signed out.
    initGoogleSignIn();
  }

  // Show editor-only toolbar controls
  const isEditor = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  const docUploadBtn = document.getElementById("doc-upload-btn");
  if (docUploadBtn) {
    docUploadBtn.style.display = isEditor ? "" : "none";
  }
  const gedcomBtn = document.getElementById("gedcom-import-btn");
  if (gedcomBtn) {
    gedcomBtn.style.display = isEditor ? "" : "none";
  }

  if (S.CONFIG?.editorsMisconfigured) {
    showToast("⚠️ EDITORS is set but Google Sign-In is not configured — no one can edit.", "error");
  }
}

// Track whether we've successfully rendered the Google button this session.
let _googleBtnRendered = false;
let _googleSdkRetries = 0;

export function _showSigninUnavailable(show) {
  const el = document.getElementById("auth-signin-unavailable");
  const btn = document.getElementById("google-signin-btn");
  if (!el) return;
  el.style.display = show ? "" : "none";
  if (btn) btn.style.display = show ? "none" : "";
}

export function initGoogleSignIn() {
  const btnContainer = document.getElementById("google-signin-btn");
  if (!btnContainer) return;

  // No client ID configured on the server → show a clear "unavailable"
  // message instead of an empty slot.
  if (!S.CONFIG?.googleClientId) {
    _showSigninUnavailable(true);
    return;
  }

  // Google SDK loads async (`<script async defer>`); if it hasn't finished
  // yet, retry a few times before giving up.
  if (typeof google === "undefined" || !google.accounts?.id) {
    if (_googleSdkRetries < 20) {
      _googleSdkRetries++;
      setTimeout(initGoogleSignIn, 150); // up to ~3 s total
    } else {
      _showSigninUnavailable(true);
    }
    return;
  }

  if (_googleBtnRendered) {
    _showSigninUnavailable(false);
    return;
  }

  try {
    google.accounts.id.initialize({
      client_id: S.CONFIG.googleClientId,
      callback: handleGoogleSignIn,
    });
    google.accounts.id.renderButton(
      btnContainer,
      { theme: "outline", size: "small", text: "signin", shape: "pill" }
    );
    _googleBtnRendered = true;
    _showSigninUnavailable(false);
  } catch (err) {
    console.warn("Google Sign-In init failed:", err);
    _showSigninUnavailable(true);
  }
}

export function initUserPillMenu() {
  const pill = document.getElementById("user-pill");
  const menu = document.getElementById("user-menu");
  if (!pill || !menu) return;

  pill.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.classList.toggle("hidden");
  });

  // Close menu when clicking outside
  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target) && e.target !== pill) {
      menu.classList.add("hidden");
    }
  });

  // Close menu on Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") menu.classList.add("hidden");
  });
}

export function initToolsMenu() {
  const btn = document.getElementById("tools-btn");
  const menu = document.getElementById("tools-menu");
  if (!btn || !menu) return;

  const close = () => {
    menu.classList.add("hidden");
    btn.setAttribute("aria-expanded", "false");
  };

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const opened = !menu.classList.toggle("hidden");
    btn.setAttribute("aria-expanded", String(opened));
  });

  // Choosing an action closes the menu; so does clicking outside or Escape.
  menu.addEventListener("click", close);
  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target) && e.target !== btn) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
}

export function populateViewingAsDropdown(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;

  // Clear existing options
  sel.innerHTML = "";

  const sorted = [...S.DATA.people]
    .filter(p => p.given_name)
    .sort((a, b) => {
      const nameA = `${a.given_name || ""} ${a.surname || ""}`.trim();
      const nameB = `${b.given_name || ""} ${b.surname || ""}`.trim();
      return nameA.localeCompare(nameB);
    });

  // Detect duplicate display names so we can disambiguate with birth year
  const nameCounts = {};
  for (const p of sorted) {
    const name = `${p.given_name || ""} ${p.surname || ""}`.trim();
    nameCounts[name] = (nameCounts[name] || 0) + 1;
  }

  for (const p of sorted) {
    const opt = document.createElement("option");
    opt.value = p.id;
    const name = `${p.given_name || ""} ${p.surname || ""}`.trim();
    if (nameCounts[name] > 1 && p.birth_date) {
      opt.textContent = `${name} (b. ${p.birth_date.substring(0, 4)})`;
    } else {
      opt.textContent = name;
    }
    if (p.id === S.CENTER_ID_A) opt.selected = true;
    sel.appendChild(opt);
  }

  sel.addEventListener("change", () => {
    setCenterPerson(sel.value);
    refreshAllViews();
  });
}

export function initViewingAs() {
  // Check URL param first
  const params = new URLSearchParams(window.location.search);
  const meParam = params.get("me");

  // Then check localStorage
  const savedMe = localStorage.getItem("ft-viewing-as");

  // If authenticated, use the auth person as default
  const authId = S.AUTH_USER?.person_id;
  const targetId = meParam || authId || savedMe || null;

  if (targetId && S.PEOPLE_MAP[targetId]) {
    setCenterPerson(targetId);
  }

  // Populate the global viewing-as dropdown (always visible)
  populateViewingAsDropdown("viewing-as-global");

  // Populate the viewing-as dropdown (inside user menu)
  populateViewingAsDropdown("viewing-as-select");

  // Wire up logout button
  const logoutBtn = document.getElementById("auth-logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
  }

  // Init user pill menu toggle
  initUserPillMenu();

  // Init the data-tools overflow menu (Import / Export / Upload / Undo)
  initToolsMenu();

  // Apply auth state to UI
  applyAuth();

  // Init Google Sign-In button (if client ID is configured)
  initGoogleSignIn();
}

// ═══════════════════════════════════════════════════════════════
// Editors Management Panel
// ═══════════════════════════════════════════════════════════════

const _ROLE_LABELS = {
  owner: "Owner",
  editor: "Editor",
  assistant: "Assistant",
  researcher: "Researcher",
};

export async function openEditorsPanel() {
  const overlay = document.getElementById("editors-overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  document.getElementById("user-menu")?.classList.add("hidden");
  await refreshEditorsList();
}

export function closeEditorsPanel() {
  const overlay = document.getElementById("editors-overlay");
  if (overlay) overlay.classList.add("hidden");
}

async function refreshEditorsList() {
  const listEl = document.getElementById("editors-list");
  if (!listEl) return;

  listEl.innerHTML = `<div class="editors-loading">Loading...</div>`;

  try {
    const resp = await fetch("/api/editors");
    if (!resp.ok) {
      listEl.innerHTML = `<div class="editors-empty">Could not load editors.</div>`;
      return;
    }
    const editors = await resp.json();
    if (editors.length === 0) {
      listEl.innerHTML = `<div class="editors-empty">No non-family editors yet. Invite one below.</div>`;
      return;
    }

    listEl.innerHTML = editors.map(e => `
      <div class="editor-row" data-email="${escapeHtml(e.email)}">
        <div class="editor-info">
          <span class="editor-name">${escapeHtml(e.name || e.email)}</span>
          ${e.name ? `<span class="editor-email-sub">${escapeHtml(e.email)}</span>` : ""}
        </div>
        <select class="editor-role-select add-relative-input" onchange="updateEditorRole('${escapeHtml(e.email)}', this.value)">
          ${Object.entries(_ROLE_LABELS).map(([k, v]) =>
            `<option value="${k}" ${e.role === k ? "selected" : ""}>${v}</option>`
          ).join("")}
        </select>
        <button class="editor-remove-btn" onclick="removeEditor('${escapeHtml(e.email)}')" title="Remove">&times;</button>
      </div>
    `).join("");
  } catch {
    listEl.innerHTML = `<div class="editors-empty">Network error.</div>`;
  }
}

export async function submitInviteEditor() {
  const emailEl = document.getElementById("editor-invite-email");
  const nameEl = document.getElementById("editor-invite-name");
  const roleEl = document.getElementById("editor-invite-role");
  const errorEl = document.getElementById("editor-invite-error");
  if (!emailEl || !roleEl) return;

  const email = emailEl.value.trim().toLowerCase();
  const name = nameEl?.value.trim() || "";
  const role = roleEl.value;

  if (!email || !email.includes("@")) {
    errorEl.textContent = "Enter a valid email address.";
    errorEl.classList.remove("hidden");
    return;
  }
  errorEl.classList.add("hidden");

  try {
    const resp = await fetch("/api/editors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, name, role }),
    });
    if (!resp.ok) {
      const data = await resp.json();
      errorEl.textContent = data.error || "Failed to add editor.";
      errorEl.classList.remove("hidden");
      return;
    }
  } catch {
    errorEl.textContent = "Network error.";
    errorEl.classList.remove("hidden");
    return;
  }

  emailEl.value = "";
  if (nameEl) nameEl.value = "";
  await refreshEditorsList();
}

export async function updateEditorRole(email, role) {
  try {
    await fetch(`/api/editors/${encodeURIComponent(email)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
  } catch {
    // Silently fail — the dropdown will reflect the old value on next refresh
  }
}

export async function removeEditor(email) {
  if (!confirm(`Remove ${email} as an editor?`)) return;
  try {
    await fetch(`/api/editors/${encodeURIComponent(email)}`, { method: "DELETE" });
  } catch {
    return;
  }
  await refreshEditorsList();
}
