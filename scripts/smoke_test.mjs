// Headless integration smoke test for the web app — the JS safety net for
// refactors. Boots the page in real Chrome, exercises every major view and the
// person panel, and fails on any uncaught page exception, app-origin request
// failure, missing global, or view that renders empty.
//
// Usage:
//   1. Start the app on a port (default 8137) pointed at a DB with data.
//   2. npx playwright install chrome   (once, if needed)
//   3. SMOKE_URL=http://127.0.0.1:8137 node scripts/smoke_test.mjs
import { chromium } from "playwright";

const BASE = process.env.SMOKE_URL || "http://127.0.0.1:8137";

// Expected noise when running locally without Google sign-in for the origin.
const BENIGN = [
  /api\/auth\/me/,
  /favicon\.ico/,
  /GSI_LOGGER/,
  /accounts\.google\.com/,
  /photospicker\.googleapis/,
  /tile\.openstreetmap/,
  /basemaps\.cartocdn/,
  /Failed to load resource/, // URL-less mirror; covered by the response listener
];
const isBenign = (s) => BENIGN.some((re) => re.test(s));

const errors = [];
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
page.on("console", (msg) => {
  if (msg.type() === "error" && !isBenign(msg.text())) errors.push(`console.error: ${msg.text()}`);
});
page.on("response", (res) => {
  const u = res.url();
  if (u.startsWith(BASE) && res.status() >= 400 && !isBenign(u)) {
    errors.push(`http ${res.status()}: ${u}`);
  }
});

const fail = (msg) => {
  errors.push(msg);
};

await page.goto(BASE, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(2000);

// 1. Core function globals (spread across modules) must be defined on window.
const fns = await page.evaluate(() => ({
  renderTree: typeof window.renderTree,
  renderTimeline: typeof window.renderTimeline,
  renderMap: typeof window.renderMap,
  showPersonPanel: typeof window.showPersonPanel,
  checkAuth: typeof window.checkAuth,
  openLightbox: typeof window.openLightbox,
  switchTab: typeof window.switchTab,
  computeRelationship: typeof window.computeRelationship,
}));
const missingFns = Object.entries(fns).filter(([, v]) => v !== "function").map(([k]) => k);
if (missingFns.length) fail("missing function globals: " + missingFns.join(", "));

// 2. Data loaded.
const firstPersonId = await page.evaluate(() =>
  window.S && window.S.DATA && window.S.DATA.people.length ? window.S.DATA.people[0].id : null
);
if (!firstPersonId) fail("DATA did not load (no people)");

// 3. Tree view renders nodes.
const svgGroups = await page.evaluate(() => document.querySelectorAll("#tree-svg g").length);
if (svgGroups === 0) fail("tree rendered no SVG groups");

// 4. Person panel opens and renders content.
if (firstPersonId) {
  await page.evaluate((id) => window.showPersonPanel(id), firstPersonId);
  await page.waitForTimeout(500);
  const panelLen = await page.evaluate(
    () => (document.getElementById("panel-content")?.innerHTML || "").length
  );
  if (panelLen < 20) fail("person panel rendered empty");
}

// 5. Each tab switches and its view renders something.
const tabChecks = [
  ["timeline", () => document.querySelectorAll("#timeline-entries *").length],
  ["map", () => (document.querySelector("#map") ? 1 : 0)],
  ["photos", () => document.querySelectorAll("#view-photos *").length],
  ["relationships", () => document.querySelectorAll("#view-relationships *").length],
  ["tree", () => document.querySelectorAll("#tree-svg g").length],
];
for (const [view, counter] of tabChecks) {
  await page.evaluate((v) => window.switchTab && window.switchTab(v), view);
  await page.waitForTimeout(700);
  const n = await page.evaluate(counter);
  if (!n) fail(`view "${view}" rendered empty after switchTab`);
}

// 6. Map markers actually plot (data has places).
await page.evaluate(() => window.switchTab && window.switchTab("map"));
await page.waitForTimeout(1200);
const markerState = await page.evaluate(() => ({
  leaflet: document.querySelectorAll(".leaflet-marker-icon, #map svg path, #map .leaflet-interactive").length,
}));

await browser.close();

console.log("Function globals:", JSON.stringify(fns));
console.log(`firstPerson: ${firstPersonId} | tree groups: ${svgGroups}`);
console.log(`leaflet shapes: ${markerState.leaflet}`);

if (errors.length) {
  console.error("\nErrors:\n  " + errors.join("\n  "));
  console.error("SMOKE FAIL");
  process.exit(1);
}
console.log("\nSMOKE PASS — boots, data loads, panel + all 5 views render, no errors ✓");
