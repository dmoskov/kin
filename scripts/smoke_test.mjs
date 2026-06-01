// Headless smoke test for the web app — the JS safety net for refactors.
//
// Usage:
//   1. Start the app on a port (default 8137), pointed at a DB with data.
//   2. npx playwright install chrome   (once, if needed)
//   3. SMOKE_URL=http://127.0.0.1:8137 node scripts/smoke_test.mjs
//
// Fails on any uncaught page exception or *app-origin* request failure, and
// asserts the core globals (spread across all split JS modules) are defined and
// that real data renders. Benign third-party / not-signed-in noise is ignored.
import { chromium } from "playwright";

const BASE = process.env.SMOKE_URL || "http://127.0.0.1:8137";

// Console/network noise that is expected when running locally without Google
// sign-in configured for the origin — not a regression.
const BENIGN = [
  /api\/auth\/me/, // 401 when not signed in
  /favicon\.ico/,
  /GSI_LOGGER/, // Google Identity can't authorize localhost
  /accounts\.google\.com/,
  /photospicker\.googleapis/,
  /tile\.openstreetmap/, // leaflet map tiles (offline)
  // URL-less console mirror of network failures; covered by the response
  // listener below, which can filter by URL.
  /Failed to load resource/,
];
const isBenign = (s) => BENIGN.some((re) => re.test(s));

const errors = [];
const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
page.on("console", (msg) => {
  if (msg.type() === "error" && !isBenign(msg.text())) {
    errors.push(`console.error: ${msg.text()}`);
  }
});
page.on("requestfailed", (req) => {
  const u = req.url();
  if (u.startsWith(BASE) && !isBenign(u)) {
    errors.push(`requestfailed: ${u} ${req.failure()?.errorText}`);
  }
});
page.on("response", (res) => {
  const u = res.url();
  if (u.startsWith(BASE) && res.status() >= 400 && !isBenign(u)) {
    errors.push(`http ${res.status()}: ${u}`);
  }
});

await page.goto(BASE, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(2000); // let init() + async render settle

// Globals defined as function declarations live on window; top-level let/const
// live in the shared global lexical env (referenced bare inside evaluate()).
const checks = await page.evaluate(() => ({
  fns: {
    renderTree: typeof window.renderTree,
    renderTimeline: typeof window.renderTimeline,
    renderMap: typeof window.renderMap,
    showPersonPanel: typeof window.showPersonPanel,
    checkAuth: typeof window.checkAuth,
    openLightbox: typeof window.openLightbox,
  },
  dataPeople: typeof DATA !== "undefined" && DATA ? DATA.people.length : 0,
}));

// Exercise every tab.
let tabbed = 0;
for (const t of await page.$$(".tab")) {
  try {
    await t.click();
    await page.waitForTimeout(400);
    tabbed++;
  } catch (e) {
    errors.push(`tab click failed: ${e.message}`);
  }
}
const svgGroups = await page.evaluate(() => document.querySelectorAll("svg g").length);

await browser.close();

console.log("Function globals:", JSON.stringify(checks.fns));
console.log(`DATA.people: ${checks.dataPeople} | tabs clicked: ${tabbed} | svg <g>: ${svgGroups}`);

const missingFns = Object.entries(checks.fns)
  .filter(([, v]) => v !== "function")
  .map(([k]) => k);

if (errors.length || missingFns.length || checks.dataPeople === 0) {
  if (errors.length) console.error("Errors:\n  " + errors.join("\n  "));
  if (missingFns.length) console.error("Missing function globals: " + missingFns.join(", "));
  if (checks.dataPeople === 0) console.error("No data rendered (DATA empty)");
  console.error("\nSMOKE FAIL");
  process.exit(1);
}
console.log("\nSMOKE PASS — app boots, all module globals defined, data renders, tabs work ✓");
