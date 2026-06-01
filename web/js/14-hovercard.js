// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

let _hovercardTimer = null;
let _hovercardVisible = false;

function buildHovercardHtml(personId) {
  const person = PEOPLE_MAP[personId];
  if (!person) return "";

  const photoHtml = person._profilePhotoPath
    ? croppedImg(person._profilePhotoPath, person.fullName, 52, person._profileCrop, "hovercard-photo")
    : "";

  let dates = "";
  if (person.birth_date) {
    const by = person.birth_date.substring(0, 4);
    dates = person.death_date
      ? `${by} - ${person.death_date.substring(0, 4)}`
      : `b. ${by}`;
  }

  const place = person.birth_place || "";

  // Viewer-relative relationship
  let relHtml = "";
  if (CENTER_ID_A && personId !== CENTER_ID_A) {
    const relLabel = calculateRelationship(CENTER_ID_A, personId);
    if (relLabel && relLabel !== "no relation found") {
      relHtml = `<div class="hovercard-rel">Your ${relLabel}</div>`;
    }
  }

  const parents = DATA.relationships
    .filter((r) => r.child_id === personId)
    .map((r) => r.parent_id);
  const children = DATA.relationships
    .filter((r) => r.parent_id === personId)
    .map((r) => r.child_id);
  const familyCount = parents.length + children.length;
  const familySummary = familyCount > 0
    ? `<div class="hovercard-family-summary">${parents.length} parent${parents.length !== 1 ? "s" : ""}, ${children.length} child${children.length !== 1 ? "ren" : ""}</div>`
    : "";

  return `
    <div class="hovercard-top" data-hovercard-profile="${personId}">
      ${photoHtml}
      <div class="hovercard-info">
        <div class="hovercard-name">${person.fullName}</div>
        ${relHtml}
        ${dates ? `<div class="hovercard-dates">${dates}</div>` : ""}
        ${place ? `<div class="hovercard-place">${place}</div>` : ""}
        ${person.gender ? `<span class="hovercard-badge ${person.gender}">${person.gender}</span>` : ""}
      </div>
      <span class="hovercard-open-arrow">&#x203A;</span>
    </div>
    ${familySummary}
  `;
}

function showHovercardAt(personId, x, y) {
  const hc = document.getElementById("hovercard");
  if (!hc) return;
  const html = buildHovercardHtml(personId);
  if (!html) return;

  hc.innerHTML = html;
  hc.classList.remove("hidden");
  _hovercardVisible = true;

  const hcRect = hc.getBoundingClientRect();
  const pad = 12;
  let top = y - hcRect.height - pad;
  if (top < 8) top = y + pad;

  let left = x - hcRect.width / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - hcRect.width - 8));

  hc.style.top = `${top}px`;
  hc.style.left = `${left}px`;
}

function showHovercard(personId, anchorEl) {
  const rect = anchorEl.getBoundingClientRect();
  showHovercardAt(personId, rect.left + rect.width / 2, rect.top);
}

function hideHovercard() {
  clearTimeout(_hovercardTimer);
  _hovercardTimer = null;
  const hc = document.getElementById("hovercard");
  if (hc) {
    hc.classList.add("hidden");
    _hovercardVisible = false;
  }
}

function scheduleHideHovercard(delay = 150) {
  clearTimeout(_hovercardTimer);
  _hovercardTimer = setTimeout(() => {
    hideHovercard();
  }, delay);
}

(function initHovercardInteractivity() {
  const hc = document.getElementById("hovercard");
  if (!hc) return;

  hc.addEventListener("mouseenter", () => {
    clearTimeout(_hovercardTimer);
  });
  hc.addEventListener("mouseleave", () => {
    scheduleHideHovercard(150);
  });
  hc.addEventListener("click", (e) => {
    const profileBtn = e.target.closest("[data-hovercard-profile]");
    if (profileBtn) {
      const pid = profileBtn.dataset.hovercardProfile;
      hideHovercard();
      showPersonPanel(pid);
      const prefix = personRoutePrefix();
      router.navigate(`${prefix}/person/${pid}`);
      const treeView = document.getElementById("view-tree");
      if (treeView && treeView.classList.contains("active")) {
        highlightNode(pid);
      }
    }
  });
})();

// ═══════════════════════════════════════════════════════════════
// Global Event Delegation (person links → panel + hovercard)
// ═══════════════════════════════════════════════════════════════

document.addEventListener("click", (e) => {
  const link = e.target.closest(".person-link");
  if (link) {
    e.preventDefault();
    e.stopPropagation();
    const pid = link.dataset.personId;
    if (pid) {
      showPersonPanel(pid);
      const prefix = personRoutePrefix();
      router.navigate(`${prefix}/person/${pid}`);
      const treeView = document.getElementById("view-tree");
      if (treeView && treeView.classList.contains("active")) {
        highlightNode(pid);
      }
    }
    return;
  }
});

document.addEventListener("mouseover", (e) => {
  const link = e.target.closest(".person-link");
  if (link) {
    clearTimeout(_hovercardTimer);
    _hovercardTimer = setTimeout(() => {
      const pid = link.dataset.personId;
      if (pid) showHovercard(pid, link);
    }, 250);
  }
});

document.addEventListener("mouseout", (e) => {
  const link = e.target.closest(".person-link");
  if (link) {
    scheduleHideHovercard(200);
  }
});

// ═══════════════════════════════════════════════════════════════
// Authentication + "Viewing as" Person Picker
// ═══════════════════════════════════════════════════════════════

