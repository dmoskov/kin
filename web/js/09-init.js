// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

export async function init() {
  const loadingEl = document.getElementById("app-loading");
  const errorEl = document.getElementById("app-error");
  document
    .getElementById("app-error-retry")
    ?.addEventListener("click", () => location.reload());
  try {
    await initApp();
    if (loadingEl) loadingEl.classList.add("hidden");
  } catch (err) {
    console.error("App failed to initialize:", err);
    if (loadingEl) loadingEl.classList.add("hidden");
    if (errorEl) {
      const detail = document.getElementById("app-error-detail");
      if (detail) detail.textContent = err?.message || "Something went wrong while loading.";
      errorEl.classList.remove("hidden");
    }
  }
}

async function initApp() {
  await loadConfig();
  await loadData();
  S._geocodeReady = prefetchGeocode();  // fire-and-forget; map awaits before rendering
  await checkAuth();
  applyConfig();
  // Set up viewer before the first render — this determines the center couple,
  // lanes, and fog-of-war for ALL views
  initViewingAs();
  // Always auto-compute lanes from the viewer's center couple
  autoComputeLanes(S.CENTER_ID_A, S.CENTER_ID_B);
  updateDynamicHeader(S.CENTER_ID_A, S.CENTER_ID_B);
  updateStats();
  renderTree();
  renderTimeline();
  populateTimelineFilter();
  // Initialize stream toggle button state
  const viewToggle = document.getElementById("timeline-view-toggle");
  if (viewToggle) viewToggle.textContent = S.SHOW_TIMELINE_STREAM ? "Hide Stream" : "Stream";
  populateRelSelectors();
  prefillRelationshipCalculator();
  initPhotoGalleryFilters();
  initGalleryUpload();
  renderPhotoGallery();

  // Show onboarding wizard if tree is empty
  if (typeof window._showOnboardingIfEmpty === "function") window._showOnboardingIfEmpty();

  document.getElementById("focus-depth-select")?.addEventListener("change", (e) => {
    if (S.FOCUS_PERSON_ID) {
      S.FOCUS_DEPTH = e.target.value === "all" ? "all" : parseInt(e.target.value, 10);
      applyFocus();
      const depthStr = S.FOCUS_DEPTH === "all" ? "all" : String(S.FOCUS_DEPTH);
      router.navigate(`/tree/focus/${S.FOCUS_PERSON_ID}/${depthStr}`, { replace: true });
    }
  });

  // Lazy-init map when tab is first shown (Leaflet needs a visible container)
  let mapInitialized = false;
  const observer = new MutationObserver(() => {
    const mapView = document.getElementById("view-map");
    if (mapView && mapView.classList.contains("active")) {
      if (!mapInitialized) {
        mapInitialized = true;
        renderMap();
      } else if (S.MAP) {
        S.MAP.invalidateSize();
      }
    }
  });
  observer.observe(document.getElementById("view-map"), { attributes: true, attributeFilter: ["class"] });

  // Resize handler
  window.addEventListener("resize", () => {
    renderTree();
    if (S.MAP) S.MAP.invalidateSize();
  });

  // Apply URL state (deep linking) — suppress history push since we're restoring
  router.apply();
}

// ═══════════════════════════════════════════════════════════════
// Theme Toggle (light / dark)
// ═══════════════════════════════════════════════════════════════

export function initTheme() {
  const saved = localStorage.getItem("ft-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  applyTheme(theme);
}

export function applyTheme(theme) {
  const btn = document.getElementById("theme-toggle");
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
    btn.innerHTML = "&#9728;";   // ☀ sun
    btn.title = "Switch to dark mode";
  } else {
    document.documentElement.removeAttribute("data-theme");
    btn.innerHTML = "&#9790;";   // ☾ moon
    btn.title = "Switch to light mode";
  }
  localStorage.setItem("ft-theme", theme);
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  applyTheme(current === "light" ? "dark" : "light");
  // Re-apply config palette for the new theme
  applyPalette();
  // Re-render tree to pick up CSS variable changes in SVG
  renderTree();
});


// ═══════════════════════════════════════════════════════════════
// Lightbox
// ═══════════════════════════════════════════════════════════════

