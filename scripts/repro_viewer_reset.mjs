// Regression repro for the "viewing-as center resets after clicking in/out
// of a person" bug and the focus-mode visibility-filter leak.
//
// Scenario 1 (center reset): pick a low-connectivity viewer, click a person
// node (opens the panel), then click the tree background (fires clearFocus).
// The center must remain the viewer — before the fix, clearFocus nulled
// CENTER_ID_A/B via an empty ORIGINAL_CENTER snapshot and _resolveCenterIds
// re-centered the tree on the most-connected person in the dataset.
//
// Scenario 2 (filter leak): mark a relationship restricted, re-apply the
// viewer filter, enter and exit focus mode. The restricted relationship must
// stay out of S.DATA — before the fix, applyFocus reset S.DATA to the raw
// unfiltered S.ORIGINAL_DATA.
//
// Usage: start the server with ALLOW_OPEN_ACCESS=1, then
//   SMOKE_URL=http://127.0.0.1:8137 node scripts/repro_viewer_reset.mjs
import { chromium } from "playwright";

const BASE = process.env.SMOKE_URL || "http://127.0.0.1:8137";
const browser = await chromium.launch(
  process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {}
);
const page = await browser.newPage();
const failures = [];

await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.S?.DATA?.people?.length > 0);

// ── Scenario 1: viewer center survives panel open + background click ──
const viewerId = await page.evaluate(() => {
  // Least-connected person that still renders a tree node — the opposite of
  // what _resolveCenterIds would auto-pick, so a reset is detectable.
  const conn = {};
  for (const r of S.DATA.relationships) {
    conn[r.parent_id] = (conn[r.parent_id] || 0) + 1;
    conn[r.child_id] = (conn[r.child_id] || 0) + 1;
  }
  const rendered = new Set(
    [...document.querySelectorAll(".node-group")].map((n) => n.__data__?.id)
  );
  const pick = Object.values(S.PEOPLE_MAP)
    .filter((p) => rendered.has(p.id))
    .sort((a, b) => (conn[a.id] || 0) - (conn[b.id] || 0))[0];
  setCenterPerson(pick.id);
  renderTree();
  return pick.id;
});

// Click a rendered person node that is not the viewer (opens the panel)...
await page.evaluate((vid) => {
  const node = [...document.querySelectorAll(".node-group")].find(
    (n) => n.__data__?.id && n.__data__.id !== vid
  );
  node.dispatchEvent(new MouseEvent("click", { bubbles: true }));
}, viewerId);
await page.waitForTimeout(300);
// ...then click the tree background (svg handler: closePersonPanel + clearFocus).
await page.evaluate(() => {
  document.querySelector("#tree-svg")
    .dispatchEvent(new MouseEvent("click", { bubbles: true }));
});
await page.waitForTimeout(300);

const after = await page.evaluate(() => ({
  center: S.CENTER_ID_A,
  viewer: S.VIEWER_ID,
}));
if (after.center !== viewerId) {
  failures.push(
    `center reset: expected ${viewerId}, got ${after.center} (viewer=${after.viewer})`
  );
}

// ── Scenario 2: visibility filter survives focus enter/exit ──
const leak = await page.evaluate((vid) => {
  // Restrict one relationship far from the viewer, as prod visibility
  // settings would, then run the viewer filter.
  const r = S.ORIGINAL_DATA.relationships.find(
    (r) => r.parent_id !== vid && r.child_id !== vid
  );
  r.visibility = "self_and_children";
  applyVisibilityFilter();
  const hidden = (rels) =>
    !rels.some((x) => x.parent_id === r.parent_id && x.child_id === r.child_id);
  const hiddenBefore = hidden(S.DATA.relationships);
  setFocus(vid);
  clearFocus();
  const hiddenAfter = hidden(S.DATA.relationships);
  r.visibility = "everyone";
  return { hiddenBefore, hiddenAfter };
}, viewerId);
if (!leak.hiddenBefore) {
  failures.push("filter setup: restricted relationship was not hidden initially");
}
if (!leak.hiddenAfter) {
  failures.push("filter leak: restricted relationship reappeared after focus enter/exit");
}

// Focus exit must also restore the viewer's center (snapshot path).
const centerAfterFocus = await page.evaluate(() => S.CENTER_ID_A);
if (centerAfterFocus !== viewerId) {
  failures.push(
    `focus exit: expected center ${viewerId}, got ${centerAfterFocus}`
  );
}

await browser.close();
if (failures.length) {
  console.error("REPRO FAIL —\n  " + failures.join("\n  "));
  process.exit(1);
}
console.log("REPRO PASS — viewer center and visibility filter survive click-in/click-out ✓");
