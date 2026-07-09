// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

let _hovercardTimer = null;
let _hovercardVisible = false;

export function buildHovercardHtml(personId) {
  const person = S.PEOPLE_MAP[personId];
  if (!person) return "";

  const isDeceased = !!person.death_date;

  const photoHtml = person._profilePhotoPath
    ? croppedImg(person._profilePhotoPath, person.fullName, 48, person._profileCrop, "hovercard-photo")
    : `<div class="hovercard-avatar ${person.gender || ""}">${escapeHtml((person.given_name || person.fullName || "?")[0].toUpperCase())}</div>`;

  let dates = "";
  if (person.birth_date) {
    const by = dateYear(person.birth_date);
    if (person.death_date) {
      const dy = dateYear(person.death_date);
      dates = `${by} – ${dy}`;
    } else {
      dates = `b. ${by}`;
    }
  }

  const nameDisplay = person.maiden_name
    ? `${escapeHtml(person.fullName)} <span class="hovercard-maiden">(née ${escapeHtml(person.maiden_name)})</span>`
    : escapeHtml(person.fullName);

  let relHtml = "";
  const relText = viewerRelationText(personId);
  if (relText) relHtml = `<div class="hovercard-rel">${relText}</div>`;

  const heritage = matchHeritage(person.birth_place);
  const heritageHtml = heritage && S.CONFIG?.heritageLabels !== false
    ? `<span class="hovercard-heritage" style="border-color:${heritage.color}40;color:${heritage.color}">${heritage.region}</span>`
    : "";

  const parents = S.DATA.relationships
    .filter((r) => r.child_id === personId)
    .map((r) => r.parent_id);
  const children = S.DATA.relationships
    .filter((r) => r.parent_id === personId)
    .map((r) => r.child_id);
  const partners = S.DATA.unions
    .filter((u) => u.partner1_id === personId || u.partner2_id === personId)
    .map((u) => (u.partner1_id === personId ? u.partner2_id : u.partner1_id));

  const parts = [];
  if (partners.length) parts.push(`${partners.length} partner${partners.length !== 1 ? "s" : ""}`);
  if (parents.length) parts.push(`${parents.length} parent${parents.length !== 1 ? "s" : ""}`);
  if (children.length) parts.push(`${children.length} child${children.length !== 1 ? "ren" : ""}`);
  const familySummary = parts.length > 0
    ? `<div class="hovercard-family-summary">${parts.join('<span class="hovercard-sep">·</span>')}</div>`
    : "";

  const deceasedCls = isDeceased ? " deceased" : "";

  return `
    <div class="hovercard-top${deceasedCls}" data-hovercard-profile="${personId}">
      ${photoHtml}
      <div class="hovercard-info">
        <div class="hovercard-name">${nameDisplay}</div>
        ${relHtml}
        <div class="hovercard-meta">
          ${dates ? `<span class="hovercard-dates">${dates}</span>` : ""}
          ${person.gender ? `<span class="hovercard-badge ${person.gender}">${genderLabel(person.gender)}</span>` : ""}
        </div>
        ${person.birth_place ? `<div class="hovercard-place">${escapeHtml(person.birth_place)}</div>` : ""}
        ${heritageHtml}
      </div>
      <span class="hovercard-open-arrow">›</span>
    </div>
    ${familySummary}
  `;
}

export function showHovercardAt(personId, x, y) {
  const hc = document.getElementById("hovercard");
  if (!hc) return;
  // Cancel any hide scheduled by a previous anchor — otherwise that stale
  // timer fires right after this card appears and blinks it away.
  clearTimeout(_hovercardTimer);
  _hovercardTimer = null;
  const html = buildHovercardHtml(personId);
  if (!html) return;

  hc.innerHTML = html;
  hc.style.transition = "none";
  hc.style.visibility = "hidden";
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

  hc.classList.add("hidden");
  hc.offsetHeight;
  hc.style.transition = "";
  hc.style.visibility = "";
  hc.classList.remove("hidden");
}

export function showHovercard(personId, anchorEl) {
  const rect = anchorEl.getBoundingClientRect();
  showHovercardAt(personId, rect.left + rect.width / 2, rect.top);
}

export function hideHovercard() {
  clearTimeout(_hovercardTimer);
  _hovercardTimer = null;
  const hc = document.getElementById("hovercard");
  if (hc) {
    hc.classList.add("hidden");
    _hovercardVisible = false;
  }
}

export function scheduleHideHovercard(delay = 150) {
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
    scheduleHideHovercard(300);
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
    scheduleHideHovercard(400);
  }
});

// ═══════════════════════════════════════════════════════════════
// Authentication + "Viewing as" Person Picker
// ═══════════════════════════════════════════════════════════════

