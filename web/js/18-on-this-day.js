// Part of the family-tree web app (ES module).
// "On this day" — a small dismissible card surfacing anniversaries whose
// full ISO date (YYYY-MM-DD) matches today's month-day: births, marriages,
// life events, and remembrances. Shows once per day; clicking a name opens
// that person's panel. Matching logic is pure and exported for tests.
import { S } from "./00-state.js";
import { escapeHtml } from "./03-data-nav.js";

const EVENT_VERBS = {
  immigration: "arrived",
  emigration: "set out",
  naturalization: "became a citizen",
  military: "began military service",
  career: "started a chapter",
  education: "started school",
  residence: "settled",
};

// Return anniversary items for monthDay ("MM-DD"). Only full YYYY-MM-DD
// dates participate — year-only and year-month dates never match.
export function buildOnThisDayItems(data, peopleMap, monthDay, nowYear) {
  if (!data || !data.people) return [];
  const items = [];
  const md = (d) => (typeof d === "string" && d.length === 10 ? d.slice(5) : null);
  const yearOf = (d) => parseInt(d.slice(0, 4), 10);
  const nameOf = (id) => peopleMap[id]?.fullName || null;

  for (const p of data.people) {
    const full = nameOf(p.id);
    if (!full) continue;
    if (md(p.birth_date) === monthDay) {
      const y = yearOf(p.birth_date);
      items.push({
        kind: "birth",
        personId: p.id,
        year: y,
        text: `${full} was born this day in ${y}`,
        detail: `${nowYear - y} years ago`,
      });
    }
    if (md(p.death_date) === monthDay) {
      const y = yearOf(p.death_date);
      items.push({
        kind: "death",
        personId: p.id,
        year: y,
        text: `Remembering ${full}, who passed this day in ${y}`,
        detail: "",
      });
    }
  }

  for (const u of data.unions || []) {
    if (md(u.union_date) !== monthDay) continue;
    const a = nameOf(u.partner1_id);
    const b = nameOf(u.partner2_id);
    if (!a || !b) continue;
    const y = yearOf(u.union_date);
    items.push({
      kind: "marriage",
      personId: u.partner1_id,
      year: y,
      text: `${a} & ${b} were married this day in ${y}`,
      detail: `${nowYear - y} years`,
    });
  }

  for (const e of data.events || []) {
    // Births/deaths/marriages are covered above from their primary records.
    if (["birth", "death", "marriage"].includes(e.event_type)) continue;
    if (md(e.date) !== monthDay) continue;
    const full = nameOf(e.person_id);
    if (!full) continue;
    const y = yearOf(e.date);
    const verb = EVENT_VERBS[e.event_type] || "marked a milestone";
    const where = e.place ? ` in ${e.place}` : "";
    items.push({
      kind: "event",
      personId: e.person_id,
      year: y,
      text: `${full} ${verb}${where} this day in ${y}`,
      detail: "",
    });
  }

  // Celebrations first, remembrances last; recent years read as more vivid.
  const ORDER = { birth: 0, marriage: 1, event: 2, death: 3 };
  items.sort((a, b) => ORDER[a.kind] - ORDER[b.kind] || b.year - a.year);
  return items;
}

export function showOnThisDayCard() {
  const today = new Date();
  const monthDay =
    `${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const dismissKey = `ft-otd-dismissed-${monthDay}`;
  try {
    if (localStorage.getItem(dismissKey)) return;
  } catch (_) { /* private mode */ }

  const items = buildOnThisDayItems(S.DATA, S.PEOPLE_MAP, monthDay, today.getFullYear());
  if (items.length === 0) return;

  document.getElementById("otd-card")?.remove();
  const card = document.createElement("aside");
  card.id = "otd-card";
  card.className = "otd-card";
  card.setAttribute("aria-label", "On this day in your family");
  const rows = items
    .map(
      (it) => `<li class="otd-item otd-${it.kind}">
        <button type="button" class="otd-link" data-person="${escapeHtml(it.personId)}">
          ${escapeHtml(it.text)}${it.detail ? ` <span class="otd-detail">· ${escapeHtml(it.detail)}</span>` : ""}
        </button>
      </li>`
    )
    .join("");
  card.innerHTML = `
    <div class="otd-head">
      <span class="otd-title">📅 On this day</span>
      <button type="button" class="otd-close" aria-label="Dismiss">&times;</button>
    </div>
    <ul class="otd-list">${rows}</ul>`;
  document.body.appendChild(card);

  const dismiss = () => {
    card.remove();
    try {
      localStorage.setItem(dismissKey, "1");
    } catch (_) { /* private mode */ }
  };
  card.querySelector(".otd-close").addEventListener("click", dismiss);
  card.querySelectorAll(".otd-link").forEach((btn) => {
    btn.addEventListener("click", () => {
      dismiss();
      if (typeof window.showPersonPanel === "function") window.showPersonPanel(btn.dataset.person);
    });
  });
}
