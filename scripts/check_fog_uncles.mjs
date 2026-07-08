// Verify the fog-of-war fix: children of blood ancestors (aunts/uncles of
// the center) must get a finite fog distance (1) instead of falling to 99.
// Usage: SMOKE_URL=http://127.0.0.1:8137 node scripts/check_fog_uncles.mjs
import { chromium } from "playwright";

const BASE = process.env.SMOKE_URL || "http://127.0.0.1:8137";
const browser = await chromium.launch(
  process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {}
);
const page = await browser.newPage();
await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.S?.DATA?.people?.length > 0);

const result = await page.evaluate(() => {
  const fog = window._fogDistance || {};
  const parentsOf = {}, childrenOf = {};
  for (const r of S.DATA.relationships) {
    (parentsOf[r.child_id] ||= []).push(r.parent_id);
    (childrenOf[r.parent_id] ||= []).push(r.child_id);
  }
  // Find every "blood aunt/uncle": a child of a fog-0 person who is not
  // fog-0 themselves (sibling of an ancestor of the center).
  const uncles = [];
  for (const [pid, d] of Object.entries(fog)) {
    if (d !== 0) continue;
    for (const kid of childrenOf[pid] || []) {
      if (fog[kid] !== 0) uncles.push({ id: kid, fog: fog[kid] });
    }
  }
  return { center: S.CENTER_ID_A, uncles };
});

console.log("center:", result.center);
console.log("ancestor-children found:", result.uncles.length);
const bad = result.uncles.filter((u) => u.fog === undefined || u.fog > 1);
for (const u of result.uncles.slice(0, 10)) console.log(" ", u.id, "fog =", u.fog);
await browser.close();

if (result.uncles.length === 0) {
  console.log("NOTE: no ancestor-siblings in this dataset — nothing to assert");
} else if (bad.length) {
  console.log("FOG FIX FAIL — uncles with fog > 1:", JSON.stringify(bad));
  process.exit(1);
} else {
  console.log("FOG FIX PASS — all blood aunts/uncles at fog 1 ✓");
}
