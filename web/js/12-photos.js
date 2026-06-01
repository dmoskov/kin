// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

let PHOTO_PICKER_PERSON = null;
let ALL_PHOTOS = null;
let _photoPickerPasteHandler = null;

// ── Toast notification ────────────────────────────────────────────────

function showToast(message, type = "success") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = `toast ${type}`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add("hidden"), 2000);
}

// ── Photo Picker ──────────────────────────────────────────────────────

// Rebuild only the photos section inside the open side panel (no full-tree
// reload, no panel-wide re-render). Called by the picker after successful
// add / remove / caption operations.
// Build the inner HTML of the panel's photos section (the photo grid plus the
// "+ Manage Photos" button). Shared by showPersonPanel (full render) and
// _renderPanelPhotos (picker-refresh render) so the markup stays in sync.
function buildPanelPhotosInnerHtml(personId) {
  const person = PEOPLE_MAP[personId];
  if (!person) return "";
  const photos = person.photo_paths || [];
  const captions = person.photo_captions || {};
  let html = "";
  if (photos.length > 0) {
    html += `<div class="panel-photos">`;
    for (const src of photos) {
      const capText = captions[src] || person.fullName;
      const safeCaption = capText.replace(/'/g, "\\'");
      const isProfile = person._profilePhotoPath === src;
      html += `<div class="panel-photo-wrap">`;
      if (isProfile) html += `<span class="photo-profile-badge" title="Profile photo">&#9733;</span>`;
      html += `<img class="panel-photo" src="/${src}" alt="${capText}" loading="lazy" onclick="openLightbox('/${src}', '${safeCaption}', '${src}')" />`;
      if (captions[src]) {
        html += `<div class="panel-photo-caption">${captions[src]}</div>`;
      }
      const photoInfo = PHOTOS_MAP[src];
      if (photoInfo) {
        const others = (photoInfo.tagged_people || []).filter(tp => tp.person_id !== personId);
        if (others.length > 0) {
          html += `<div class="panel-photo-also">Also: ${others.map(tp => personLink(tp.person_id, [tp.given_name, tp.surname].filter(Boolean).join(" "))).join(", ")}</div>`;
        }
      }
      if (photoInfo && (photoInfo.date || photoInfo.place)) {
        const dateStr = photoInfo.date_circa ? `c. ${photoInfo.date}` : photoInfo.date;
        html += `<div class="panel-photo-meta">`;
        if (photoInfo.date) html += `<span>${dateStr}</span>`;
        if (photoInfo.date && photoInfo.place) html += ` &middot; `;
        if (photoInfo.place) html += `<span>${photoInfo.place}</span>`;
        html += `</div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
  }
  if (!CONFIG?.editorsEnabled || AUTH_USER?.is_editor) {
    html += `<button class="panel-add-photo-btn" onclick="openPhotoPicker('${personId}')">+ Manage Photos</button>`;
  }
  return html;
}

function _renderPanelPhotos(personId) {
  const person = PEOPLE_MAP[personId];
  if (!person) return;
  const section = document.querySelector("#panel-content .panel-photos-section");
  if (!section) return; // panel isn't currently showing this person
  section.innerHTML = buildPanelPhotosInnerHtml(personId);
}

// Wire up a caption <input> to save on blur/Enter without rebuilding
// anything on success — so focus and cursor position are never lost.
function _wireCaptionInput(input, personId) {
  let _saving = false;
  let _lastSaved = input.value;
  const saveCaption = async () => {
    if (_saving) return;
    const photo = input.dataset.photo;
    const caption = input.value.trim();
    if (caption === _lastSaved) return; // no-op
    _saving = true;
    try {
      const resp = await fetch(`/api/people/${personId}/photo-caption`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_path: photo, caption }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        showToast(data.error || "Could not save caption", "error");
        return;
      }
      _lastSaved = caption;
      const person = PEOPLE_MAP[personId];
      if (person) {
        person.photo_captions = person.photo_captions || {};
        if (caption) person.photo_captions[photo] = caption;
        else delete person.photo_captions[photo];
      }
      _renderPanelPhotos(personId);
      showToast("Caption saved");
    } catch (err) {
      showToast("Could not save caption: " + err.message, "error");
    } finally {
      _saving = false;
    }
  };
  input.addEventListener("blur", saveCaption);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); input.blur(); }
  });
  // Stop click propagation so clicking input doesn't toggle the photo tile.
  input.addEventListener("click", (e) => e.stopPropagation());
}

function _isProfilePhoto(personId, photoPath) {
  const person = PEOPLE_MAP[personId];
  return person && person._profilePhotoPath === photoPath;
}

function _buildPhotoMetadataFields(photoPath) {
  const photoData = PHOTOS_MAP[photoPath];
  if (!photoData) return "";
  const date = photoData.date || "";
  const circa = photoData.date_circa ? "checked" : "";
  const place = photoData.place || "";
  const ptype = photoData.photo_type || "photo";
  return `
    <div class="photo-meta-fields" data-photo="${photoPath}">
      <div class="photo-meta-row">
        <input class="photo-meta-date" type="text" placeholder="Date (e.g. 1987-04)" value="${date}" data-field="date" />
        <label class="photo-meta-circa"><input type="checkbox" ${circa} data-field="date_circa" /> Circa</label>
      </div>
      <input class="photo-meta-place" type="text" placeholder="Place" value="${place.replace(/"/g, '&quot;')}" data-field="place" />
      <select class="photo-meta-type" data-field="photo_type">
        <option value="photo" ${ptype === "photo" ? "selected" : ""}>Photo</option>
        <option value="portrait" ${ptype === "portrait" ? "selected" : ""}>Portrait</option>
        <option value="group" ${ptype === "group" ? "selected" : ""}>Group</option>
        <option value="document" ${ptype === "document" ? "selected" : ""}>Document</option>
        <option value="headstone" ${ptype === "headstone" ? "selected" : ""}>Headstone</option>
      </select>
    </div>
  `;
}

function _buildTagChips(photoPath, currentPersonId) {
  const photoData = PHOTOS_MAP[photoPath];
  if (!photoData) return "";
  const otherPeople = (photoData.tagged_people || []).filter(tp => tp.person_id !== currentPersonId);
  if (otherPeople.length === 0) {
    return `<div class="photo-tag-chips"><button class="photo-tag-add" data-photo="${photoPath}">+ Tag person</button></div>`;
  }
  let chips = otherPeople.map(tp => {
    const name = [tp.given_name, tp.surname].filter(Boolean).join(" ") || tp.person_id;
    return `<span class="photo-tag-chip" data-person="${tp.person_id}" data-photo="${photoPath}">${name} <span class="photo-tag-remove">&times;</span></span>`;
  }).join("");
  return `<div class="photo-tag-chips">${chips}<button class="photo-tag-add" data-photo="${photoPath}">+ Tag</button></div>`;
}

function _openTagSearch(anchorBtn, currentPersonId) {
  // Remove any existing search dropdown
  document.querySelectorAll(".photo-tag-search").forEach(el => el.remove());

  const photoPath = anchorBtn.dataset.photo;
  const photoData = PHOTOS_MAP[photoPath];
  if (!photoData) return;

  const dropdown = document.createElement("div");
  dropdown.className = "photo-tag-search";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Search people...";
  input.className = "photo-tag-search-input";
  const results = document.createElement("div");
  results.className = "photo-tag-search-results";
  dropdown.appendChild(input);
  dropdown.appendChild(results);
  anchorBtn.parentElement.appendChild(dropdown);

  const alreadyTagged = new Set((photoData.tagged_people || []).map(tp => tp.person_id));
  alreadyTagged.add(currentPersonId);

  input.addEventListener("input", () => {
    const q = input.value.toLowerCase().trim();
    if (!q) { results.innerHTML = ""; return; }
    const matches = Object.values(PEOPLE_MAP)
      .filter(p => !alreadyTagged.has(p.id) && p.fullName.toLowerCase().includes(q))
      .slice(0, 5);
    results.innerHTML = matches.map(p =>
      `<div class="photo-tag-search-result" data-id="${p.id}">${personThumb(p.id, 20)} ${p.fullName}</div>`
    ).join("");
    results.querySelectorAll(".photo-tag-search-result").forEach(el => {
      el.addEventListener("click", async () => {
        const tagId = el.dataset.id;
        try {
          const resp = await fetch(`/api/photos/${photoData.id}/tag`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ person_id: tagId }),
          });
          if (resp.ok) {
            const person = PEOPLE_MAP[tagId];
            photoData.tagged_people = photoData.tagged_people || [];
            photoData.tagged_people.push({
              person_id: tagId,
              is_profile: false,
              caption: "",
              given_name: person?.given_name || "",
              surname: person?.surname || "",
            });
            dropdown.remove();
            _buildPickerGrid(currentPersonId);
            showToast(`Tagged ${person?.fullName || tagId}`);
          }
        } catch (err) {
          showToast("Could not tag person: " + err.message, "error");
        }
      });
    });
  });

  input.focus();
  // Close on outside click
  setTimeout(() => {
    document.addEventListener("click", function handler(e) {
      if (!dropdown.contains(e.target)) {
        dropdown.remove();
        document.removeEventListener("click", handler);
      }
    });
  }, 0);
}

function _buildPickerGrid(personId) {
  const person = PEOPLE_MAP[personId];
  if (!person) return;

  const grid = document.getElementById("photo-picker-grid");
  const assigned = new Set(person.photo_paths || []);
  const captions = person.photo_captions || {};

  grid.innerHTML = ALL_PHOTOS.map((photo) => {
    const sel = assigned.has(photo) ? "selected" : "";
    const cap = captions[photo] || "";
    return `
      <div class="photo-picker-item ${sel}" data-photo="${photo}">
        <img src="/${photo}" alt="${photo}" loading="lazy" />
        <div class="check">&#10003;</div>
        ${sel ? `<button class="photo-profile-star ${_isProfilePhoto(personId, photo) ? 'active' : ''}" data-photo="${photo}" title="Set as profile photo">&#9733;</button>` : ""}
        ${sel ? `<button class="photo-crop-btn" data-photo="${photo}" title="Crop for profile">&#8910;</button>` : ""}
        ${sel && (PHOTOS_MAP[photo]?.face_regions || []).length > 0 ? `<span class="photo-face-badge" title="Has face tags">&#9786;</span>` : ""}
        ${sel ? `<input class="photo-caption-input" type="text" placeholder="Add caption..." value="${cap.replace(/"/g, '&quot;')}" data-photo="${photo}" />` : ""}
        ${sel ? _buildPhotoMetadataFields(photo) : ""}
        ${sel ? _buildTagChips(photo, personId) : ""}
      </div>
    `;
  }).join("");

  // Click image area to toggle assignment. Uses optimistic UI + targeted
  // DOM updates so we never reload the tree or rebuild the side panel —
  // that was causing flashes and losing caption focus.
  grid.querySelectorAll(".photo-picker-item").forEach((item) => {
    const img = item.querySelector("img");
    const checkEl = item.querySelector(".check");
    let _busy = false;

    const toggleHandler = async (e) => {
      // Don't toggle if clicking the caption input.
      if (e.target.classList.contains("photo-caption-input")) return;
      if (_busy) return;
      _busy = true;

      const photo = item.dataset.photo;
      const wasSelected = item.classList.contains("selected");

      // Optimistic UI: toggle tile class and add/remove caption input
      // inline without rebuilding the grid.
      item.classList.toggle("selected");
      if (!wasSelected) {
        if (!item.querySelector(".photo-caption-input")) {
          const input = document.createElement("input");
          input.className = "photo-caption-input";
          input.type = "text";
          input.placeholder = "Add caption...";
          input.dataset.photo = photo;
          input.value = (PEOPLE_MAP[personId]?.photo_captions || {})[photo] || "";
          _wireCaptionInput(input, personId);
          item.appendChild(input);
        }
      } else {
        const inp = item.querySelector(".photo-caption-input");
        if (inp) inp.remove();
      }

      try {
        let resp;
        if (wasSelected) {
          resp = await fetch(`/api/people/${personId}/photos`, {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ photo_path: photo }),
          });
        } else {
          resp = await fetch(`/api/people/${personId}/photos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ photo_paths: [photo] }),
          });
        }
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          // Revert optimistic UI.
          item.classList.toggle("selected");
          if (!wasSelected) {
            const inp = item.querySelector(".photo-caption-input");
            if (inp) inp.remove();
          }
          showToast(data.error || "Could not update photos", "error");
          return;
        }

        // Update local cache from server's authoritative response so
        // the side panel re-renders with the correct set.
        const p = PEOPLE_MAP[personId];
        if (p && Array.isArray(data.photo_paths)) {
          p.photo_paths = data.photo_paths;
          if (wasSelected && p.photo_captions) {
            delete p.photo_captions[photo];
          }
        }
        _renderPanelPhotos(personId);
        showToast(wasSelected ? "Photo removed" : "Photo assigned");
      } catch (err) {
        // Revert optimistic UI on network failure.
        item.classList.toggle("selected");
        if (!wasSelected) {
          const inp = item.querySelector(".photo-caption-input");
          if (inp) inp.remove();
        }
        showToast("Network error: " + err.message, "error");
      } finally {
        _busy = false;
      }
    };

    img.addEventListener("click", toggleHandler);
    checkEl.addEventListener("click", toggleHandler);
  });

  // Wire caption inputs for already-selected tiles.
  grid.querySelectorAll(".photo-caption-input").forEach((input) => {
    _wireCaptionInput(input, personId);
  });

  // Wire profile-star click handlers
  grid.querySelectorAll(".photo-profile-star").forEach((star) => {
    star.addEventListener("click", async (e) => {
      e.stopPropagation();
      const photoPath = star.dataset.photo;
      const photoData = PHOTOS_MAP[photoPath];
      if (!photoData) return;
      try {
        const resp = await fetch(`/api/people/${personId}/profile-photo`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ photo_id: photoData.id }),
        });
        if (resp.ok) {
          const person = PEOPLE_MAP[personId];
          if (person) person._profilePhotoPath = photoPath;
          grid.querySelectorAll(".photo-profile-star").forEach(s => s.classList.remove("active"));
          star.classList.add("active");
          _renderPanelPhotos(personId);
          showToast("Profile photo updated");
        }
      } catch (err) {
        showToast("Could not set profile photo: " + err.message, "error");
      }
    });
  });

  // Wire tag-add buttons
  grid.querySelectorAll(".photo-tag-add").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      _openTagSearch(btn, personId);
    });
  });

  // Wire tag-remove buttons
  grid.querySelectorAll(".photo-tag-remove").forEach((x) => {
    x.addEventListener("click", async (e) => {
      e.stopPropagation();
      const chip = x.closest(".photo-tag-chip");
      const photoPath = chip.dataset.photo;
      const tagPersonId = chip.dataset.person;
      const photoData = PHOTOS_MAP[photoPath];
      if (!photoData) return;
      try {
        const resp = await fetch(`/api/photos/${photoData.id}/tag/${tagPersonId}`, { method: "DELETE" });
        if (resp.ok) {
          photoData.tagged_people = (photoData.tagged_people || []).filter(tp => tp.person_id !== tagPersonId);
          chip.remove();
          showToast("Tag removed");
        }
      } catch (err) {
        showToast("Could not remove tag: " + err.message, "error");
      }
    });
  });

  // Wire photo metadata autosave
  grid.querySelectorAll(".photo-meta-fields").forEach((container) => {
    const photoPath = container.dataset.photo;
    const photoData = PHOTOS_MAP[photoPath];
    if (!photoData) return;

    const saveMetadata = async () => {
      const date = container.querySelector('[data-field="date"]')?.value.trim() || null;
      const date_circa = container.querySelector('[data-field="date_circa"]')?.checked || false;
      const place = container.querySelector('[data-field="place"]')?.value.trim() || null;
      const photo_type = container.querySelector('[data-field="photo_type"]')?.value || "photo";
      try {
        const resp = await fetch(`/api/photos/${photoData.id}/metadata`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ date, date_circa, place, photo_type }),
        });
        if (resp.ok) {
          const updated = await resp.json();
          Object.assign(photoData, updated);
          showToast("Photo metadata saved");
        }
      } catch (err) {
        showToast("Could not save metadata: " + err.message, "error");
      }
    };

    container.querySelectorAll("input[type=text], select").forEach(el => {
      el.addEventListener("blur", saveMetadata);
      el.addEventListener("change", saveMetadata);
      el.addEventListener("click", (e) => e.stopPropagation());
    });
    container.querySelectorAll("input[type=checkbox]").forEach(el => {
      el.addEventListener("change", saveMetadata);
      el.addEventListener("click", (e) => e.stopPropagation());
    });
  });

  // Wire crop buttons
  grid.querySelectorAll(".photo-crop-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openCropModal(personId, btn.dataset.photo);
    });
  });
}

function openCropModal(personId, photoPath) {
  const person = PEOPLE_MAP[personId];
  if (!person) return;
  const photoData = PHOTOS_MAP[photoPath];

  const existing = document.getElementById("crop-modal");
  if (existing) existing.remove();

  const currentCrop = person._profileCrop || { x: 0, y: 0, w: 1, h: 1 };
  let crop = { ...currentCrop };

  const modal = document.createElement("div");
  modal.id = "crop-modal";
  modal.className = "crop-modal";

  // Find face region for this person on this photo
  const faceRegion = photoData
    ? (photoData.face_regions || []).find(fr => fr.person_id === personId)
    : null;

  modal.innerHTML = `
    <div class="crop-modal-backdrop"></div>
    <div class="crop-modal-dialog">
      <h3>Crop Profile Photo</h3>
      <p class="crop-modal-hint">Drag to pan, scroll to zoom</p>
      <div class="crop-viewport">
        <img class="crop-image" src="/${photoPath}" alt="Crop preview" draggable="false" />
      </div>
      <div class="crop-modal-actions">
        ${faceRegion ? `<button class="crop-center-face">Center on face</button>` : ""}
        <button class="crop-reset">Reset</button>
        <button class="crop-save">Save</button>
        <button class="crop-cancel">Cancel</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const img = modal.querySelector(".crop-image");
  const viewport = modal.querySelector(".crop-viewport");

  function applyCrop() {
    const scale = 1 / crop.w;
    const vpSize = viewport.offsetWidth;
    img.style.width = (vpSize * scale) + "px";
    img.style.height = "auto";
    img.style.left = (-crop.x * vpSize * scale) + "px";
    img.style.top = (-crop.y * vpSize * scale) + "px";
  }

  img.addEventListener("load", applyCrop);
  if (img.complete) setTimeout(applyCrop, 0);

  // Drag to pan
  let dragging = false, dragStartX, dragStartY, dragStartCrop;
  viewport.addEventListener("mousedown", (e) => {
    e.preventDefault();
    dragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragStartCrop = { ...crop };
  });
  document.addEventListener("mousemove", function cropMove(e) {
    if (!dragging) return;
    const vpSize = viewport.offsetWidth;
    const scale = 1 / crop.w;
    const dx = (e.clientX - dragStartX) / (vpSize * scale);
    const dy = (e.clientY - dragStartY) / (vpSize * scale);
    crop.x = Math.max(0, Math.min(1 - crop.w, dragStartCrop.x - dx));
    crop.y = Math.max(0, Math.min(1 - crop.h, dragStartCrop.y - dy));
    applyCrop();
  });
  document.addEventListener("mouseup", function cropUp() { dragging = false; });

  // Scroll to zoom
  viewport.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
    const newW = Math.max(0.05, Math.min(1, crop.w * zoomFactor));
    const newH = Math.max(0.05, Math.min(1, crop.h * zoomFactor));
    // Keep center point stable
    const cx = crop.x + crop.w / 2;
    const cy = crop.y + crop.h / 2;
    crop.w = newW;
    crop.h = newH;
    crop.x = Math.max(0, Math.min(1 - crop.w, cx - crop.w / 2));
    crop.y = Math.max(0, Math.min(1 - crop.h, cy - crop.h / 2));
    applyCrop();
  });

  // Center on face
  if (faceRegion) {
    modal.querySelector(".crop-center-face").addEventListener("click", () => {
      const pad = 0.2;
      const fx = Math.max(0, faceRegion.x - faceRegion.w * pad);
      const fy = Math.max(0, faceRegion.y - faceRegion.h * pad);
      const fw = Math.min(1 - fx, faceRegion.w * (1 + 2 * pad));
      const fh = Math.min(1 - fy, faceRegion.h * (1 + 2 * pad));
      const side = Math.max(fw, fh);
      crop.x = Math.max(0, Math.min(1 - side, fx - (side - fw) / 2));
      crop.y = Math.max(0, Math.min(1 - side, fy - (side - fh) / 2));
      crop.w = Math.min(side, 1 - crop.x);
      crop.h = Math.min(side, 1 - crop.y);
      applyCrop();
    });
  }

  // Reset
  modal.querySelector(".crop-reset").addEventListener("click", () => {
    crop = { x: 0, y: 0, w: 1, h: 1 };
    applyCrop();
  });

  // Cancel
  const closeModal = () => modal.remove();
  modal.querySelector(".crop-cancel").addEventListener("click", closeModal);
  modal.querySelector(".crop-modal-backdrop").addEventListener("click", closeModal);

  // Save
  modal.querySelector(".crop-save").addEventListener("click", async () => {
    if (!photoData) { closeModal(); return; }
    // If reset to full image, clear crop
    if (crop.x === 0 && crop.y === 0 && crop.w >= 0.99 && crop.h >= 0.99) {
      try {
        await fetch(`/api/people/${personId}/profile-crop`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ photo_id: photoData.id }),
        });
        person._profileCrop = null;
        showToast("Profile crop cleared");
      } catch (err) {
        showToast("Could not clear crop: " + err.message, "error");
      }
    } else {
      try {
        await fetch(`/api/people/${personId}/profile-crop`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ photo_id: photoData.id, crop_x: crop.x, crop_y: crop.y, crop_w: crop.w, crop_h: crop.h }),
        });
        person._profileCrop = { ...crop };
        showToast("Profile crop saved");
      } catch (err) {
        showToast("Could not save crop: " + err.message, "error");
      }
    }
    closeModal();
  });
}

async function openPhotoPicker(personId) {
  PHOTO_PICKER_PERSON = personId;
  const person = PEOPLE_MAP[personId];
  if (!person) return;

  const overlay = document.getElementById("photo-picker-overlay");
  const title = document.getElementById("photo-picker-title");

  title.textContent = `Photos — ${person.fullName}`;

  // Load available photos (cache after first load)
  if (!ALL_PHOTOS) {
    const resp = await fetch("/api/photos");
    const raw = await resp.json();
    // API may return rich objects or flat strings (pre-migration)
    ALL_PHOTOS = raw.map(p => typeof p === "string" ? p : p.file_path);
  }

  _buildPickerGrid(personId);

  // Wire up upload zone
  const uploadZone = document.getElementById("photo-upload-zone");
  const fileInput = document.getElementById("photo-file-input");
  const progressEl = document.getElementById("upload-progress");
  const progressText = document.getElementById("upload-progress-text");

  // Remove old listeners by cloning
  const newZone = uploadZone.cloneNode(true);
  uploadZone.parentNode.replaceChild(newZone, uploadZone);

  const newFileInput = newZone.querySelector("#photo-file-input");
  const newProgressEl = newZone.querySelector("#upload-progress");
  const newProgressText = newZone.querySelector("#upload-progress-text");

  // Click zone → open file picker
  newZone.addEventListener("click", (e) => {
    if (e.target === newFileInput || e.target.tagName === "LABEL") return;
    newFileInput.click();
  });

  // Drag events
  newZone.addEventListener("dragover", (e) => { e.preventDefault(); newZone.classList.add("drag-over"); });
  newZone.addEventListener("dragleave", () => newZone.classList.remove("drag-over"));
  newZone.addEventListener("drop", async (e) => {
    e.preventDefault();
    newZone.classList.remove("drag-over");
    await _uploadFiles(e.dataTransfer.files, personId, newProgressEl, newProgressText);
  });

  // File input change
  newFileInput.addEventListener("change", async () => {
    await _uploadFiles(newFileInput.files, personId, newProgressEl, newProgressText);
    newFileInput.value = "";
  });

  // Clipboard paste — listen on the whole overlay so paste works whenever
  // the picker is visible, regardless of which element has focus.
  const pasteHandler = async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles = [];
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length === 0) return;
    e.preventDefault();
    await _uploadFiles(imageFiles, personId, newProgressEl, newProgressText);
  };
  if (_photoPickerPasteHandler) {
    document.removeEventListener("paste", _photoPickerPasteHandler);
  }
  _photoPickerPasteHandler = pasteHandler;
  document.addEventListener("paste", _photoPickerPasteHandler);

  // Show/hide Google Photos import button based on config
  _updateGooglePhotosBtn();

  overlay.classList.remove("hidden");
}

async function _uploadFiles(files, personId, progressEl, progressText) {
  if (!files || files.length === 0) return;

  progressEl.classList.remove("hidden");
  let uploaded = 0;
  const total = files.length;
  const errors = [];

  for (let i = 0; i < total; i++) {
    let file = files[i];
    // Counter uses the index so it advances even on individual failures,
    // instead of getting stuck on "Uploading 1 of N..." forever.
    progressText.textContent = `Uploading ${i + 1} of ${total}: ${file.name}`;

    // Resize large images client-side before upload
    file = await resizeImageFile(file);

    const formData = new FormData();
    formData.append("photo", file);

    try {
      const resp = await fetch("/api/photos/upload", { method: "POST", body: formData });
      // The server returns JSON even on 4xx/5xx; try to parse regardless.
      const data = await resp.json().catch(() => ({}));

      if (resp.ok && data.path) {
        // Auto-assign to this person.
        const assignResp = await fetch(`/api/people/${PHOTO_PICKER_PERSON}/photos`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ photo_paths: [data.path] }),
        });
        const assignData = await assignResp.json().catch(() => ({}));
        if (assignResp.ok) {
          if (Array.isArray(assignData.photo_paths)) {
            const p = PEOPLE_MAP[PHOTO_PICKER_PERSON];
            if (p) p.photo_paths = assignData.photo_paths;
          }
          if (!ALL_PHOTOS.includes(data.path)) ALL_PHOTOS.push(data.path);
          uploaded++;
        } else {
          errors.push(`${file.name}: ${assignData.error || "could not attach"}`);
        }
      } else {
        errors.push(`${file.name}: ${data.error || "upload failed"}`);
      }
    } catch (err) {
      errors.push(`${file.name}: ${err.message}`);
    }
  }

  progressEl.classList.add("hidden");

  if (uploaded > 0) {
    showToast(`${uploaded} photo${uploaded > 1 ? "s" : ""} uploaded`);
    // Refresh just what's needed — no full-tree reload.
    _renderPanelPhotos(personId);
    _buildPickerGrid(personId);
  }
  if (errors.length > 0) {
    // Show the first error in detail; if more than one, summarize.
    const msg = errors.length === 1
      ? errors[0]
      : `${errors.length} of ${total} uploads failed — ${errors[0]}`;
    showToast(msg, "error");
    // Log the full list so the user can inspect in devtools if needed.
    console.warn("Photo upload errors:", errors);
  }
}

function closePhotoPicker() {
  if (_photoPickerPasteHandler) {
    document.removeEventListener("paste", _photoPickerPasteHandler);
    _photoPickerPasteHandler = null;
  }
  document.getElementById("photo-picker-overlay").classList.add("hidden");
  PHOTO_PICKER_PERSON = null;
}

document.getElementById("photo-picker-close").addEventListener("click", closePhotoPicker);
document.getElementById("photo-picker-overlay").addEventListener("click", (e) => {
  if (e.target.id === "photo-picker-overlay") closePhotoPicker();
});

// ═══════════════════════════════════════════════════════════════
// Google Photos Picker Integration (new Photos Picker API)
//
// Uses the session-based Google Photos Picker API with the
// non-sensitive `photospicker.mediaitems.readonly` scope.
// No app verification or scary warnings required.
//
// Flow:
//   1. Get OAuth token (photospicker.mediaitems.readonly)
//   2. POST /v1/sessions → create picker session
//   3. Open pickerUri in popup
//   4. Poll session until user finishes picking
//   5. GET session/mediaItems → download URLs
//   6. Send to server for download + attachment
// ═══════════════════════════════════════════════════════════════

