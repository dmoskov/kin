import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { JSDOM } from "jsdom";

let dom;
let document;

beforeAll(() => {
  const html = readFileSync(
    resolve(import.meta.dirname, "../../web/index.html"),
    "utf-8"
  );
  dom = new JSDOM(html);
  document = dom.window.document;
});

describe("Accessibility basics", () => {
  it("has lang attribute on <html>", () => {
    expect(document.documentElement.getAttribute("lang")).toBe("en");
  });

  it("has a skip-to-content link as first focusable element", () => {
    const skip = document.querySelector("body > a.sr-only");
    expect(skip).not.toBeNull();
    expect(skip.getAttribute("href")).toMatch(/^#/);
    expect(skip.textContent).toMatch(/skip/i);
  });

  it("has exactly one <h1>", () => {
    const h1s = document.querySelectorAll("h1");
    expect(h1s.length).toBe(1);
  });

  it("has a <main> landmark", () => {
    expect(document.querySelector("main")).not.toBeNull();
  });

  it("all img elements have alt attributes", () => {
    const imgs = document.querySelectorAll("img");
    for (const img of imgs) {
      const hasAlt =
        img.hasAttribute("alt") || img.getAttribute("aria-hidden") === "true";
      expect(hasAlt, `img missing alt: ${img.outerHTML.slice(0, 100)}`).toBe(
        true
      );
    }
  });

  it("all interactive controls have accessible names", () => {
    const buttons = document.querySelectorAll("button");
    for (const btn of buttons) {
      const name =
        btn.textContent.trim() ||
        btn.getAttribute("aria-label") ||
        btn.getAttribute("title");
      expect(
        !!name,
        `button missing accessible name: ${btn.outerHTML.slice(0, 120)}`
      ).toBe(true);
    }
  });

  it("all form inputs have labels or aria-label", () => {
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="file"]), select, textarea'
    );
    for (const input of inputs) {
      if (input.closest('[style*="display:none"]')) continue;
      const id = input.id;
      const hasLabel =
        input.getAttribute("aria-label") ||
        input.getAttribute("aria-labelledby") ||
        input.getAttribute("title") ||
        (id && document.querySelector(`label[for="${id}"]`));
      expect(
        !!hasLabel,
        `input missing label: ${input.outerHTML.slice(0, 120)}`
      ).toBe(true);
    }
  });

  it("tab buttons have correct ARIA tab roles", () => {
    const tabs = document.querySelectorAll('[role="tab"]');
    expect(tabs.length).toBeGreaterThan(0);
    for (const tab of tabs) {
      expect(tab.hasAttribute("aria-controls")).toBe(true);
      expect(tab.hasAttribute("aria-selected")).toBe(true);
    }
  });

  it("each tabpanel is linked to its tab", () => {
    const panels = document.querySelectorAll('[role="tabpanel"]');
    expect(panels.length).toBeGreaterThan(0);
    for (const panel of panels) {
      expect(panel.hasAttribute("aria-labelledby")).toBe(true);
      const tabId = panel.getAttribute("aria-labelledby");
      expect(document.getElementById(tabId)).not.toBeNull();
    }
  });

  it("dialogs have role and aria-label", () => {
    const dialogs = document.querySelectorAll('[role="dialog"]');
    expect(dialogs.length).toBeGreaterThan(0);
    for (const dialog of dialogs) {
      const label =
        dialog.getAttribute("aria-label") ||
        dialog.getAttribute("aria-labelledby");
      expect(
        !!label,
        `dialog missing label: ${dialog.id || dialog.className}`
      ).toBe(true);
    }
  });

  it("toast element is a live region", () => {
    const toast = document.getElementById("toast");
    expect(toast).not.toBeNull();
    expect(toast.getAttribute("role")).toBe("status");
    expect(toast.getAttribute("aria-live")).toBe("polite");
  });

  it("close buttons have aria-label", () => {
    const closeButtons = document.querySelectorAll(
      ".close-btn, .modal-close, .photo-picker-close, .editors-panel-close"
    );
    for (const btn of closeButtons) {
      expect(
        !!btn.getAttribute("aria-label"),
        `close button missing aria-label: ${btn.outerHTML.slice(0, 100)}`
      ).toBe(true);
    }
  });

  it("search input has combobox role and aria attributes", () => {
    const search = document.getElementById("global-search");
    expect(search.getAttribute("role")).toBe("combobox");
    expect(search.hasAttribute("aria-controls")).toBe(true);
    expect(search.hasAttribute("aria-expanded")).toBe(true);
    expect(search.hasAttribute("aria-label")).toBe(true);
  });

  it("tree depth controls use radiogroup pattern", () => {
    const group = document.querySelector('[role="radiogroup"]');
    expect(group).not.toBeNull();
    const radios = group.querySelectorAll('[role="radio"]');
    expect(radios.length).toBeGreaterThan(0);
    const checked = Array.from(radios).filter(
      (r) => r.getAttribute("aria-checked") === "true"
    );
    expect(checked.length).toBe(1);
  });
});
