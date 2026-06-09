// Visual-diff harness for design work. Boots the app in real Chrome, bypasses
// the local sign-in gate (backend is open-access when GOOGLE_CLIENT_ID is unset),
// and screenshots every view in light + dark at desktop + mobile widths.
//
// Usage: start the server on :8137, then
//   PW_CHANNEL=chrome SMOKE_URL=http://127.0.0.1:8137 node scripts/design_shots.mjs
// Output: /tmp/ft-shots/<theme>-<width>-<view>.png
import { chromium } from "playwright";
import fs from "fs";

const BASE = process.env.SMOKE_URL || "http://127.0.0.1:8137";
const OUT = "/tmp/ft-shots";
fs.mkdirSync(OUT, { recursive: true });

const VIEWS = ["tree", "timeline", "map", "photos", "relationships"];
const WIDTHS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const THEMES = (process.env.THEMES || "dark,light").split(",");
const ONLY = process.env.ONLY ? process.env.ONLY.split(",") : VIEWS;

const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});

for (const theme of THEMES) {
  for (const [wname, viewport] of Object.entries(WIDTHS)) {
    if (process.env.WIDTHS && !process.env.WIDTHS.split(",").includes(wname)) continue;
    const page = await browser.newPage({ viewport, deviceScaleFactor: 2 });
    await page.route("**/api/config", async (route) => {
      const res = await route.fetch();
      const json = await res.json();
      delete json.googleClientId;
      await route.fulfill({ response: res, body: JSON.stringify(json), contentType: "application/json" });
    });
    await page.addInitScript((t) => { try { localStorage.setItem("ft-theme", t); } catch (e) {} }, theme);
    await page.goto(BASE, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(2500);
    for (const v of ONLY) {
      await page.evaluate((vv) => window.switchTab && window.switchTab(vv), v);
      await page.waitForTimeout(v === "map" ? 1800 : 900);
      await page.screenshot({ path: `${OUT}/${theme}-${wname}-${v}.png` });
      console.log(`shot ${theme}-${wname}-${v}`);
    }
    if (ONLY.includes("tree") && process.env.PANEL !== "0") {
      await page.evaluate((vv) => window.switchTab && window.switchTab(vv), "tree");
      await page.waitForTimeout(600);
      const pid = await page.evaluate(() => window.S?.DATA?.people?.length ? window.S.DATA.people[0].id : null);
      if (pid) {
        await page.evaluate((id) => window.showPersonPanel(id), pid);
        await page.waitForTimeout(800);
        await page.screenshot({ path: `${OUT}/${theme}-${wname}-panel.png` });
        console.log(`shot ${theme}-${wname}-panel`);
      }
    }
    await page.close();
  }
}
await browser.close();
console.log("DONE");
