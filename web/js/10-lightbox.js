// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

// Images sourced from Wikimedia Commons are named "wikimedia-<slug>.<ext>".
// Build a Commons media-search link from the slug so the source is credited.
function _wikimediaSource(path) {
  if (!path) return "";
  const base = path.split("/").pop().replace(/\.[a-z0-9]+$/i, "");
  if (!base.toLowerCase().startsWith("wikimedia-")) return "";
  const terms = base.slice(10).replace(/-/g, " ").replace(/\b\d{6,}\b/g, "").replace(/\s+/g, " ").trim();
  return "https://commons.wikimedia.org/w/index.php?title=Special:MediaSearch&type=image&search=" + encodeURIComponent(terms);
}

export function openLightbox(src, alt, photoPath, photoList, contextPersonId) {
  const existing = document.getElementById("lightbox");
  if (existing) existing.remove();

  const isEditor = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  let currentPhotoPath = photoPath;
  let currentSrc = src;
  let currentAlt = alt;

  const hasNav = Array.isArray(photoList) && photoList.length > 1;
  let currentIdx = hasNav ? photoList.indexOf(photoPath) : -1;
  if (currentIdx < 0 && hasNav) currentIdx = 0;

  const overlay = document.createElement("div");
  overlay.id = "lightbox";
  overlay.innerHTML = `
    <div class="lightbox-backdrop"></div>
    <div class="lightbox-content">
      ${hasNav ? `<button class="lightbox-nav lightbox-prev" aria-label="Previous photo">&#8249;</button>` : ""}
      <div class="lightbox-main">
        <div class="lightbox-img-wrap">
          <img src="${src}" alt="${alt}" />
        </div>
        <div class="lightbox-caption">${escapeHtml(alt)}</div>
        <div class="lightbox-source"></div>
        <div class="lightbox-tags"></div>
        ${hasNav ? `<div class="lightbox-counter">${currentIdx + 1} / ${photoList.length}</div>` : ""}
      </div>
      ${hasNav ? `<button class="lightbox-nav lightbox-next" aria-label="Next photo">&#8250;</button>` : ""}
      <button class="lightbox-close">&times;</button>
    </div>
  `;
  document.body.appendChild(overlay);

  const imgWrap = overlay.querySelector(".lightbox-img-wrap");
  const img = imgWrap.querySelector("img");
  const captionEl = overlay.querySelector(".lightbox-caption");
  const counterEl = overlay.querySelector(".lightbox-counter");
  const sourceEl = overlay.querySelector(".lightbox-source");
  let ro = null;

  function updateSource() {
    if (!sourceEl) return;
    const url = _wikimediaSource(currentPhotoPath);
    sourceEl.innerHTML = url
      ? `<a href="${url}" target="_blank" rel="noopener">Source: Wikimedia Commons &#8599;</a>`
      : "";
  }
  updateSource();

  function getPhotoData() {
    return currentPhotoPath ? S.PHOTOS_MAP[currentPhotoPath] : null;
  }

  const tagsEl = overlay.querySelector(".lightbox-tags");
  function renderTags() {
    if (!tagsEl) return;
    const pd = getPhotoData();
    const tags = (pd && pd.tagged_people) || [];
    if (!tags.length) { tagsEl.innerHTML = ""; return; }
    tagsEl.innerHTML =
      `<span class="lightbox-tags-label">In this photo:</span>` +
      tags.map((t) => {
        const nm = [t.given_name, t.surname].filter(Boolean).join(" ") ||
          (S.PEOPLE_MAP[t.person_id] && S.PEOPLE_MAP[t.person_id].fullName) || "Unknown";
        return `<button type="button" class="lightbox-tag-chip" data-person-id="${t.person_id}">${personThumb(t.person_id, 22)}<span>${escapeHtml(nm)}</span></button>`;
      }).join("");
    tagsEl.querySelectorAll(".lightbox-tag-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const pid = chip.dataset.personId;
        close();
        if (pid && typeof showPersonPanel === "function") showPersonPanel(pid);
      });
    });
  }
  renderTags();

  function renderFaceRegions() {
    imgWrap.querySelectorAll(".face-region-overlay").forEach(el => el.remove());
    const pd = getPhotoData();
    const regions = pd?.face_regions || [];
    if (regions.length === 0) return;

    const imgRect = img.getBoundingClientRect();
    const natW = img.naturalWidth || 1;
    const natH = img.naturalHeight || 1;
    const scale = Math.min(imgRect.width / natW, imgRect.height / natH);
    const dispW = natW * scale;
    const dispH = natH * scale;
    const offX = (imgRect.width - dispW) / 2;
    const offY = (imgRect.height - dispH) / 2;

    const inAnnotation = imgWrap.classList.contains("annotation-mode");

    for (const fr of regions) {
      const name = [fr.given_name, fr.surname].filter(Boolean).join(" ");
      const div = document.createElement("div");
      div.className = "face-region-overlay";
      div.style.left = (offX + fr.x * dispW) + "px";
      div.style.top = (offY + fr.y * dispH) + "px";
      div.style.width = (fr.w * dispW) + "px";
      div.style.height = (fr.h * dispH) + "px";
      div.innerHTML = `<span class="face-region-label">${escapeHtml(name)}</span>`;
      if (inAnnotation) {
        const del = document.createElement("button");
        del.className = "face-region-delete";
        del.textContent = "\u00d7";
        del.addEventListener("click", async (e) => {
          e.stopPropagation();
          try {
            await fetch(`/api/photos/${pd.id}/face-region/${fr.id}`, { method: "DELETE" });
            pd.face_regions = (pd.face_regions || []).filter(r => r.id !== fr.id);
            renderFaceRegions();
            showToast("Face tag removed");
          } catch (err) {
            showToast("Could not remove face tag: " + err.message, "error");
          }
        });
        div.appendChild(del);
      }
      imgWrap.appendChild(div);
    }
  }

  function showPhoto(idx) {
    if (!hasNav) return;
    if (idx < 0) idx = photoList.length - 1;
    if (idx >= photoList.length) idx = 0;
    currentIdx = idx;
    currentPhotoPath = photoList[currentIdx];
    currentSrc = "/" + currentPhotoPath;
    const person = contextPersonId ? S.PEOPLE_MAP[contextPersonId] : null;
    const captions = person?.photo_captions || {};
    currentAlt = captions[currentPhotoPath] || person?.fullName || "";
    img.src = currentSrc;
    img.alt = currentAlt;
    captionEl.textContent = currentAlt;
    updateSource();
    renderTags();
    if (counterEl) counterEl.textContent = `${currentIdx + 1} / ${photoList.length}`;
    imgWrap.classList.remove("annotation-mode");
    const tagBtn = overlay.querySelector(".lightbox-tag-faces-btn");
    if (tagBtn) tagBtn.classList.remove("active");
    renderFaceRegions();
  }

  const close = () => {
    if (ro) ro.disconnect();
    overlay.remove();
    document.removeEventListener("keydown", keyHandler);
    if (window.location.pathname.startsWith("/photos/view/")) router.navigate("/photos");
  };

  function keyHandler(e) {
    if (e.key === "Escape") { close(); return; }
    if (hasNav && (e.key === "ArrowRight" || e.key === "ArrowDown")) {
      e.preventDefault();
      showPhoto(currentIdx + 1);
    }
    if (hasNav && (e.key === "ArrowLeft" || e.key === "ArrowUp")) {
      e.preventDefault();
      showPhoto(currentIdx - 1);
    }
  }

  overlay.querySelector(".lightbox-backdrop").addEventListener("click", close);
  overlay.querySelector(".lightbox-close").addEventListener("click", close);
  document.addEventListener("keydown", keyHandler);

  if (hasNav) {
    overlay.querySelector(".lightbox-prev").addEventListener("click", (e) => {
      e.stopPropagation();
      showPhoto(currentIdx - 1);
    });
    overlay.querySelector(".lightbox-next").addEventListener("click", (e) => {
      e.stopPropagation();
      showPhoto(currentIdx + 1);
    });

    let touchStartX = 0;
    let touchDeltaX = 0;
    overlay.querySelector(".lightbox-main").addEventListener("touchstart", (e) => {
      touchStartX = e.touches[0].clientX;
      touchDeltaX = 0;
    }, { passive: true });
    overlay.querySelector(".lightbox-main").addEventListener("touchmove", (e) => {
      touchDeltaX = e.touches[0].clientX - touchStartX;
    }, { passive: true });
    overlay.querySelector(".lightbox-main").addEventListener("touchend", () => {
      if (Math.abs(touchDeltaX) > 40) {
        showPhoto(touchDeltaX > 0 ? currentIdx - 1 : currentIdx + 1);
      }
    });
  }

  // Face region overlays
  img.addEventListener("load", renderFaceRegions);
  if (img.complete) renderFaceRegions();

  ro = new ResizeObserver(renderFaceRegions);
  ro.observe(img);

  // Tag Faces annotation mode
  if (isEditor) {
    const tagBtn = document.createElement("button");
    tagBtn.className = "lightbox-tag-faces-btn";
    tagBtn.textContent = "Tag Faces";
    overlay.querySelector(".lightbox-main").appendChild(tagBtn);

    tagBtn.addEventListener("click", () => {
      const pd = getPhotoData();
      if (!pd) return;
      const active = imgWrap.classList.toggle("annotation-mode");
      tagBtn.classList.toggle("active", active);
      renderFaceRegions();

      if (active) {
        let startX, startY, drawDiv;

        function getImageCoords(e) {
          const imgRect = img.getBoundingClientRect();
          const natW = img.naturalWidth || 1;
          const natH = img.naturalHeight || 1;
          const scale = Math.min(imgRect.width / natW, imgRect.height / natH);
          const dispW = natW * scale;
          const dispH = natH * scale;
          const offX = (imgRect.width - dispW) / 2;
          const offY = (imgRect.height - dispH) / 2;
          const wrapRect = imgWrap.getBoundingClientRect();
          return {
            nx: (e.clientX - wrapRect.left - offX) / dispW,
            ny: (e.clientY - wrapRect.top - offY) / dispH,
            offX, offY, dispW, dispH
          };
        }

        function onMouseDown(e) {
          if (e.target.closest(".face-region-overlay")) return;
          e.preventDefault();
          const coords = getImageCoords(e);
          startX = coords.nx;
          startY = coords.ny;
          drawDiv = document.createElement("div");
          drawDiv.className = "face-region-drawing";
          const wrapRect = imgWrap.getBoundingClientRect();
          drawDiv.style.left = (e.clientX - wrapRect.left) + "px";
          drawDiv.style.top = (e.clientY - wrapRect.top) + "px";
          drawDiv.style.width = "0px";
          drawDiv.style.height = "0px";
          imgWrap.appendChild(drawDiv);

          function onMouseMove(e2) {
            const c2 = getImageCoords(e2);
            const x1 = Math.min(startX, c2.nx);
            const y1 = Math.min(startY, c2.ny);
            const x2 = Math.max(startX, c2.nx);
            const y2 = Math.max(startY, c2.ny);
            drawDiv.style.left = (c2.offX + x1 * c2.dispW) + "px";
            drawDiv.style.top = (c2.offY + y1 * c2.dispH) + "px";
            drawDiv.style.width = ((x2 - x1) * c2.dispW) + "px";
            drawDiv.style.height = ((y2 - y1) * c2.dispH) + "px";
          }

          function onMouseUp(e2) {
            document.removeEventListener("mousemove", onMouseMove);
            document.removeEventListener("mouseup", onMouseUp);
            const c2 = getImageCoords(e2);
            const x = Math.max(0, Math.min(1, Math.min(startX, c2.nx)));
            const y = Math.max(0, Math.min(1, Math.min(startY, c2.ny)));
            const w = Math.min(1 - x, Math.abs(c2.nx - startX));
            const h = Math.min(1 - y, Math.abs(c2.ny - startY));
            drawDiv.remove();

            if (w < 0.02 || h < 0.02) return;

            _openFaceTagSearch(imgWrap, pd, x, y, w, h, e2, renderFaceRegions);
          }

          document.addEventListener("mousemove", onMouseMove);
          document.addEventListener("mouseup", onMouseUp);
        }

        imgWrap._annotationHandler = onMouseDown;
        imgWrap.addEventListener("mousedown", onMouseDown);
      } else {
        if (imgWrap._annotationHandler) {
          imgWrap.removeEventListener("mousedown", imgWrap._annotationHandler);
          delete imgWrap._annotationHandler;
        }
      }
    });
  }
}

export function _openFaceTagSearch(container, photoData, x, y, w, h, mouseEvent, renderCb) {
  document.querySelectorAll(".face-tag-search").forEach(el => el.remove());

  const dropdown = document.createElement("div");
  dropdown.className = "face-tag-search";
  dropdown.style.left = (mouseEvent.clientX - container.getBoundingClientRect().left) + "px";
  dropdown.style.top = (mouseEvent.clientY - container.getBoundingClientRect().top) + "px";

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Search people...";
  input.className = "face-tag-search-input";
  const results = document.createElement("div");
  results.className = "face-tag-search-results";
  dropdown.appendChild(input);
  dropdown.appendChild(results);
  container.appendChild(dropdown);

  // Prioritize already-tagged people as suggestions (they're likely in the photo)
  const taggedIds = (photoData.tagged_people || []).map(tp => tp.person_id);

  function showResults(q) {
    let matches;
    if (!q) {
      matches = taggedIds.map(id => S.PEOPLE_MAP[id]).filter(Boolean).slice(0, 5);
    } else {
      matches = Object.values(S.PEOPLE_MAP)
        .filter(p => p.fullName.toLowerCase().includes(q))
        .slice(0, 5);
    }
    results.innerHTML = matches.map(p =>
      `<div class="face-tag-search-result" data-id="${p.id}">${personThumb(p.id, 20)} ${p.fullName}</div>`
    ).join("") || (q ? "<div class='face-tag-no-results'>No matches</div>" : "");
    results.querySelectorAll(".face-tag-search-result").forEach(el => {
      el.addEventListener("click", async () => {
        const personId = el.dataset.id;
        try {
          const resp = await fetch(`/api/photos/${photoData.id}/face-region`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ person_id: personId, x, y, w, h }),
          });
          if (resp.ok) {
            const region = await resp.json();
            const person = S.PEOPLE_MAP[personId];
            photoData.face_regions = photoData.face_regions || [];
            photoData.face_regions.push({
              id: region.id,
              person_id: personId,
              x, y, w, h,
              given_name: person?.given_name || "",
              surname: person?.surname || "",
            });
            dropdown.remove();
            renderCb();

            // If the backend auto-tagged this person in the photo, update local state
            if (region.auto_tagged && person) {
              photoData.tagged_people = photoData.tagged_people || [];
              if (!photoData.tagged_people.some(tp => tp.person_id === personId)) {
                photoData.tagged_people.push({
                  person_id: personId,
                  is_profile: false,
                  caption: "",
                  given_name: person.given_name || "",
                  surname: person.surname || "",
                });
              }
              if (!person.photo_paths?.includes(photoData.file_path)) {
                person.photo_paths = [...(person.photo_paths || []), photoData.file_path];
              }
            }
            showToast(`Face tagged: ${person?.fullName || personId}`);

            // Auto-set profile crop if this is the person's profile photo and no crop exists
            if (person && person._profilePhotoPath === photoData.file_path && !person._profileCrop) {
              const pad = 0.2;
              const cx = Math.max(0, x - w * pad);
              const cy = Math.max(0, y - h * pad);
              const cw = Math.min(1 - cx, w * (1 + 2 * pad));
              const ch = Math.min(1 - cy, h * (1 + 2 * pad));
              // Make square using the larger dimension
              const side = Math.max(cw, ch);
              const sx = Math.max(0, Math.min(1 - side, cx - (side - cw) / 2));
              const sy = Math.max(0, Math.min(1 - side, cy - (side - ch) / 2));
              const ss = Math.min(side, 1 - sx, 1 - sy);
              person._profileCrop = { x: sx, y: sy, w: ss, h: ss };
              fetch(`/api/people/${personId}/profile-crop`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ photo_id: photoData.id, crop_x: sx, crop_y: sy, crop_w: ss, crop_h: ss }),
              }).catch(() => {});
              showToast("Profile crop set from face tag");
            }
          }
        } catch (err) {
          showToast("Could not save face tag: " + err.message, "error");
        }
      });
    });
  }

  input.addEventListener("input", () => showResults(input.value.toLowerCase().trim()));
  showResults("");
  input.focus();

  setTimeout(() => {
    document.addEventListener("click", function handler(e) {
      if (!dropdown.contains(e.target)) {
        dropdown.remove();
        document.removeEventListener("click", handler);
      }
    });
  }, 0);
}

// ── Document Upload & AI Parsing ──────────────────────────────────────

