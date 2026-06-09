// Part of the family-tree web app (ES module).
// Research queue — turns data gaps (missing dates, places, photos, events)
// into a worklist. Opened from the tools menu (editors see the entry; the
// list itself is read-only and harmless for viewers). Clicking a person
// opens their panel, where every gap is one edit away. The gap computation
// is pure and exported for tests.
import { S } from "./00-state.js";
import { escapeHtml, dateYear } from "./03-data-nav.js";

// Order matters: it's the chip order in the UI summary.
export const GAP_KINDS = [
  ["birth date", (p) => !p.birth_date],
  ["birth place", (p) => !p.birth_place],
  ["death date", (p, ctx) => !p.death_date && ctx.probablyDeceased],
  ["death place", (p) => !!p.death_date && !p.death_place],
  ["photo", (p, ctx) => !ctx.hasPhoto],
  ["life events", (p, ctx) => !ctx.hasEvents],
];

export function computeResearchGaps(data, peopleMap, nowYear) {
  if (!data || !data.people) return [];
  const eventCounts = {};
  for (const e of data.events || []) eventCounts[e.person_id] = (eventCounts[e.person_id] || 0) + 1;

  const out = [];
  for (const p of data.people) {
    const person = peopleMap[p.id] || p;
    const birthYear = p.birth_date ? parseInt(String(p.birth_date).slice(0, 4), 10) : null;
    const ctx = {
      probablyDeceased: !!birthYear && nowYear - birthYear > 105,
      hasPhoto: !!person._profilePhotoPath,
      hasEvents: (eventCounts[p.id] || 0) > 0,
    };
    const gaps = GAP_KINDS.filter(([, test]) => test(p, ctx)).map(([label]) => label);
    if (gaps.length === 0) continue;
    const years = [dateYear(p.birth_date), dateYear(p.death_date)].filter(Boolean).join("–");
    out.push({
      id: p.id,
      name: person.fullName || [p.given_name, p.surname].filter(Boolean).join(" "),
      years,
      gaps,
    });
  }
  // The emptiest records float to the top — they need the most attention.
  out.sort((a, b) => b.gaps.length - a.gaps.length || a.name.localeCompare(b.name));
  return out;
}

let _activeFilter = null;

export function openResearchQueue() {
  const nowYear = new Date().getFullYear();
  const rows = computeResearchGaps(S.DATA, S.PEOPLE_MAP, nowYear);
  _activeFilter = null;

  document.getElementById("research-queue-overlay")?.remove();
  const overlay = document.createElement("div");
  overlay.id = "research-queue-overlay";
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="research-queue-modal" role="dialog" aria-label="Research gaps">
      <div class="modal-header">
        <h3>Research gaps</h3>
        <button class="modal-close" id="research-queue-close" aria-label="Close">&times;</button>
      </div>
      <p class="modal-desc" id="research-queue-summary"></p>
      <div class="research-queue-chips" id="research-queue-chips"></div>
      <ul class="research-queue-list" id="research-queue-list"></ul>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  overlay.querySelector("#research-queue-close").addEventListener("click", close);

  const summaryEl = overlay.querySelector("#research-queue-summary");
  const chipsEl = overlay.querySelector("#research-queue-chips");
  const listEl = overlay.querySelector("#research-queue-list");

  const total = S.DATA?.people?.length || 0;
  summaryEl.textContent = rows.length
    ? `${rows.length} of ${total} people have gaps worth researching. Click a person to open their panel and fill one in.`
    : "Every person has dates, places, a photo, and life events. Remarkable!";

  const renderChips = () => {
    const counts = {};
    for (const r of rows) for (const g of r.gaps) counts[g] = (counts[g] || 0) + 1;
    chipsEl.innerHTML = GAP_KINDS.filter(([label]) => counts[label])
      .map(
        ([label]) => `<button type="button" class="rq-chip${_activeFilter === label ? " active" : ""}" data-gap="${label}">
          ${escapeHtml(label)} · ${counts[label]}
        </button>`
      )
      .join("");
    chipsEl.querySelectorAll(".rq-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        _activeFilter = _activeFilter === chip.dataset.gap ? null : chip.dataset.gap;
        renderChips();
        renderList();
      });
    });
  };

  const renderList = () => {
    const visible = _activeFilter ? rows.filter((r) => r.gaps.includes(_activeFilter)) : rows;
    listEl.innerHTML = visible
      .map(
        (r) => `<li>
          <button type="button" class="rq-row" data-person="${escapeHtml(r.id)}">
            <span class="rq-name">${escapeHtml(r.name)}${r.years ? ` <span class="rq-years">${escapeHtml(r.years)}</span>` : ""}</span>
            <span class="rq-gaps">${r.gaps.map((g) => `<span class="rq-gap">${escapeHtml(g)}</span>`).join("")}</span>
          </button>
        </li>`
      )
      .join("");
    listEl.querySelectorAll(".rq-row").forEach((row) => {
      row.addEventListener("click", () => {
        close();
        if (typeof window.showPersonPanel === "function") window.showPersonPanel(row.dataset.person);
      });
    });
  };

  renderChips();
  renderList();
}

document.getElementById("research-queue-btn")?.addEventListener("click", () => {
  document.getElementById("tools-menu")?.classList.add("hidden");
  openResearchQueue();
});
