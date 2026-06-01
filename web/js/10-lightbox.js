// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

export function openLightbox(src, alt, photoPath) {
  const existing = document.getElementById("lightbox");
  if (existing) existing.remove();

  const isEditor = !S.CONFIG?.editorsEnabled || S.AUTH_USER?.is_editor;
  const photoData = photoPath ? S.PHOTOS_MAP[photoPath] : null;

  const overlay = document.createElement("div");
  overlay.id = "lightbox";
  overlay.innerHTML = `
    <div class="lightbox-backdrop"></div>
    <div class="lightbox-content">
      <div class="lightbox-img-wrap">
        <img src="${src}" alt="${alt}" />
      </div>
      <div class="lightbox-caption">${escapeHtml(alt)}</div>
      ${photoData && isEditor ? `<button class="lightbox-tag-faces-btn">Tag Faces</button>` : ""}
      <button class="lightbox-close">&times;</button>
    </div>
  `;
  document.body.appendChild(overlay);

  const close = () => {
    overlay.remove();
    if (window.location.pathname.startsWith("/photos/view/")) router.navigate("/photos");
  };
  overlay.querySelector(".lightbox-backdrop").addEventListener("click", close);
  overlay.querySelector(".lightbox-close").addEventListener("click", close);
  document.addEventListener("keydown", function handler(e) {
    if (e.key === "Escape") { close(); document.removeEventListener("keydown", handler); }
  });

  // Face region overlays
  if (photoData) {
    const imgWrap = overlay.querySelector(".lightbox-img-wrap");
    const img = imgWrap.querySelector("img");

    function renderFaceRegions() {
      imgWrap.querySelectorAll(".face-region-overlay").forEach(el => el.remove());
      const regions = photoData.face_regions || [];
      if (regions.length === 0) return;

      const imgRect = img.getBoundingClientRect();
      const wrapRect = imgWrap.getBoundingClientRect();
      // Account for object-fit: contain letterboxing
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
              await fetch(`/api/photos/${photoData.id}/face-region/${fr.id}`, { method: "DELETE" });
              photoData.face_regions = (photoData.face_regions || []).filter(r => r.id !== fr.id);
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

    img.addEventListener("load", renderFaceRegions);
    if (img.complete) renderFaceRegions();

    const ro = new ResizeObserver(renderFaceRegions);
    ro.observe(img);
    const origClose = close;
    overlay.querySelector(".lightbox-backdrop").removeEventListener("click", origClose);
    overlay.querySelector(".lightbox-close").removeEventListener("click", origClose);
    const cleanup = () => {
      ro.disconnect(); overlay.remove();
      if (window.location.pathname.startsWith("/photos/view/")) router.navigate("/photos");
    };
    overlay.querySelector(".lightbox-backdrop").addEventListener("click", cleanup);
    overlay.querySelector(".lightbox-close").addEventListener("click", cleanup);

    // Tag Faces annotation mode
    const tagBtn = overlay.querySelector(".lightbox-tag-faces-btn");
    if (tagBtn) {
      tagBtn.addEventListener("click", () => {
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

              if (w < 0.02 || h < 0.02) return; // too small

              // Show person search dropdown
              _openFaceTagSearch(imgWrap, photoData, x, y, w, h, e2, renderFaceRegions);
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

