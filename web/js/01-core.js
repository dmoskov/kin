// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

/**
 * Family Tree Dashboard
 *
 * Loads family data from /api/data (served from SQLite DB) and renders:
 * 1. Interactive D3 tree visualization (generations top-to-bottom)
 * 2. Timeline view (chronological events)
 * 3. Relationship calculator (how are two people related?)
 */

// ═══════════════════════════════════════════════════════════════
// Image Resize Utility
// ═══════════════════════════════════════════════════════════════

/**
 * Resize an image File on the client if it exceeds maxDim pixels on either side.
 * Returns a new File (JPEG) if resized, or the original File if no resize needed
 * or if it's not a resizable image type (e.g. PDF).
 */
function resizeImageFile(file, maxDim = 4096, quality = 0.85) {
  return new Promise((resolve) => {
    // Only resize raster image types
    if (!file.type.startsWith("image/") || file.type === "image/gif") {
      resolve(file);
      return;
    }

    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const { width, height } = img;

      // No resize needed
      if (width <= maxDim && height <= maxDim) {
        resolve(file);
        return;
      }

      // Compute scaled dimensions
      const scale = maxDim / Math.max(width, height);
      const newW = Math.round(width * scale);
      const newH = Math.round(height * scale);

      const canvas = document.createElement("canvas");
      canvas.width = newW;
      canvas.height = newH;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, newW, newH);

      canvas.toBlob((blob) => {
        if (!blob) { resolve(file); return; }
        // Preserve original filename but change extension to .jpg
        const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
        const resized = new File([blob], name, { type: "image/jpeg" });
        console.log(`[resize] ${file.name}: ${width}x${height} (${(file.size/1e6).toFixed(1)}MB) → ${newW}x${newH} (${(resized.size/1e6).toFixed(1)}MB)`);
        resolve(resized);
      }, "image/jpeg", quality);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(file);
    };
    img.src = url;
  });
}

// ═══════════════════════════════════════════════════════════════
// Data & Config Loading
// ═══════════════════════════════════════════════════════════════

let DATA = null;
let PEOPLE_MAP = {};
let CONFIG = null;
let FOCUS_PERSON_ID = null;
let FOCUS_DEPTH = 1;
let ORIGINAL_DATA = null;
let ORIGINAL_CENTER_ID_A = null;
let ORIGINAL_CENTER_ID_B = null;
let PHOTOS_MAP = {};

async function loadConfig() {
  try {
    const resp = await fetch("/api/config");
    CONFIG = await resp.json();
  } catch (_) {
    CONFIG = { familyName: "Family Tree", subtitle: "", heritage: [], palette: {}, timelinePhotos: true, heritageLabels: false };
  }
}

function applyConfig() {
  if (!CONFIG) return;

  // Center IDs from config — only as initial defaults (viewer selection takes precedence)
  if (CONFIG.centerIdA && !CENTER_ID_A) CENTER_ID_A = CONFIG.centerIdA;
  if (CONFIG.centerIdB && !CENTER_ID_B) CENTER_ID_B = CONFIG.centerIdB;

  // Config lanes are no longer used — lanes are always auto-computed from the
  // viewer's center couple to keep the experience viewer-relative.

  // Header personalization (just defaults; updateDynamicHeader overrides when a viewer is set)
  const titleEl = document.getElementById("family-title");
  const subtitleEl = document.getElementById("family-subtitle");
  if (CONFIG.familyName) titleEl.textContent = CONFIG.familyName;
  // If no familyName configured, it will be set dynamically after lanes
  // are computed (see _updateHeaderFromLanes called after autoComputeLanes)
  if (CONFIG.subtitle) subtitleEl.textContent = CONFIG.subtitle;
  else subtitleEl.style.display = "none";

  // Apply fonts
  const root = document.documentElement;
  if (CONFIG.headerFont) root.style.setProperty("--header-font", CONFIG.headerFont);
  if (CONFIG.bodyFont) root.style.setProperty("--body-font", CONFIG.bodyFont);

  // Apply palette (theme-aware)
  applyPalette();
}

function applyPalette() {
  if (!CONFIG?.palette) return;
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  const pal = isLight ? CONFIG.palette.light : CONFIG.palette.dark;
  if (!pal) return;

  const root = document.documentElement;
  const mapping = {
    bg: "--bg", surface: "--surface", surfaceHover: "--surface-hover",
    border: "--border", text: "--text", textMuted: "--text-muted",
    accent: "--accent", accentHover: "--accent-hover",
    male: "--male", female: "--female", union: "--union",
    eventBirth: "--event-birth", eventCareer: "--event-career",
    eventEdu: "--event-education", eventCustom: "--event-custom",
    eventMarriage: "--event-marriage",
    nodeMaleBg: "--node-male-bg", nodeFemaleBg: "--node-female-bg",
    nodeText: "--node-text", nodeTextDim: "--node-text-dim",
    nodeTextFaint: "--node-text-faint",
  };
  for (const [key, prop] of Object.entries(mapping)) {
    if (pal[key]) root.style.setProperty(prop, pal[key]);
  }
}

/**
 * Match a place string to a heritage region from config.
 * Returns the matching heritage entry or null.
 */
function matchHeritage(place) {
  if (!place || !CONFIG?.heritage?.length) return null;
  for (const h of CONFIG.heritage) {
    for (const m of (h.match || [])) {
      if (place.includes(m)) return h;
    }
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════
// Lane Assignment (grandparent lines — configured via family-config.json)
// ═══════════════════════════════════════════════════════════════

