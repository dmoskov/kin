// Vitest jsdom setup — stub browser APIs missing from jsdom so the ES modules
// import without crashing. All stubs are installed before any module is loaded.

// matchMedia is not implemented in jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() { return false; },
  }),
});

// localStorage is available in jsdom but referenced at module parse time in 00-state.js
// (S.SHOW_TIMELINE_STREAM). jsdom provides it, nothing extra needed.

// d3 is referenced by 04-tree.js renderTree / zoom functions at the bottom of the
// module as addEventListener wires. Those are safe because they use optional
// chaining (?.) on DOM elements that don't exist in jsdom. However buildButterflyLayout
// calls _resolveCenterIds which does NOT use d3, and computeFogDistance does not use d3.
// We only import the pure exported functions, so d3 is never actually called.
// Provide a minimal stub to avoid ReferenceError if any module-level code touches it.
globalThis.d3 = new Proxy({}, {
  get(_, key) {
    const noop = () => noop;
    noop.select = () => noop;
    noop.selectAll = () => noop;
    noop.append = () => noop;
    noop.attr = () => noop;
    noop.on = () => noop;
    return noop;
  },
});
