// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

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
export function resizeImageFile(file, maxDim = 4096, quality = 0.85) {
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


export async function loadConfig() {
  try {
    const resp = await fetch("/api/config");
    S.CONFIG = await resp.json();
  } catch (_) {
    S.CONFIG = { familyName: "Family Tree", subtitle: "", heritage: [], palette: {}, timelinePhotos: true, heritageLabels: false };
  }
}

export function applyConfig() {
  if (!S.CONFIG) return;

  // Center IDs from config — only as initial defaults (viewer selection takes precedence)
  if (S.CONFIG.centerIdA && !S.CENTER_ID_A) S.CENTER_ID_A = S.CONFIG.centerIdA;
  if (S.CONFIG.centerIdB && !S.CENTER_ID_B) S.CENTER_ID_B = S.CONFIG.centerIdB;

  // Config lanes are no longer used — lanes are always auto-computed from the
  // viewer's center couple to keep the experience viewer-relative.

  // Header personalization (just defaults; updateDynamicHeader overrides when a viewer is set)
  const titleEl = document.getElementById("family-title");
  const subtitleEl = document.getElementById("family-subtitle");
  if (S.CONFIG.familyName) titleEl.textContent = S.CONFIG.familyName;
  // If no familyName configured, it will be set dynamically after lanes
  // are computed (see _updateHeaderFromLanes called after autoComputeLanes)
  if (S.CONFIG.subtitle) subtitleEl.textContent = S.CONFIG.subtitle;
  else subtitleEl.style.display = "none";

  // Apply fonts
  const root = document.documentElement;
  if (S.CONFIG.headerFont) root.style.setProperty("--header-font", S.CONFIG.headerFont);
  if (S.CONFIG.bodyFont) root.style.setProperty("--body-font", S.CONFIG.bodyFont);

  // Apply palette (theme-aware)
  applyPalette();
}

export function applyPalette() {
  if (!S.CONFIG?.palette) return;
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  const pal = isLight ? S.CONFIG.palette.light : S.CONFIG.palette.dark;
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
export function matchHeritage(place) {
  if (!place || !S.CONFIG?.heritage?.length) return null;
  for (const h of S.CONFIG.heritage) {
    for (const m of (h.match || [])) {
      if (place.includes(m)) return h;
    }
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════
// Lane Assignment (grandparent lines — configured via family-config.json)
// ═══════════════════════════════════════════════════════════════

