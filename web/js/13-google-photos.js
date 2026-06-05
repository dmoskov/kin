// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";

let _googleOAuthToken = null;
let _pickerPopup = null;
let _pickerPollTimer = null;

export const _PHOTOS_PICKER_SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly";
export const _PHOTOS_PICKER_API = "https://photospicker.googleapis.com/v1";

/**
 * Show or hide the "From Google Photos" button based on config.
 * Called during openPhotoPicker.
 */
export function _updateGooglePhotosBtn() {
  const btn = document.getElementById("google-photos-btn");
  if (!btn) return;
  if (S.CONFIG?.googleClientId && S.CONFIG?.googlePhotosEnabled !== false) {
    btn.classList.remove("hidden");
  } else {
    btn.classList.add("hidden");
  }
}

/**
 * Get an OAuth2 access token for the Photos Picker API.
 * Uses the non-sensitive photospicker.mediaitems.readonly scope.
 */
export function _getPhotosPickerToken() {
  return new Promise((resolve, reject) => {
    if (typeof google === "undefined" || !google.accounts?.oauth2) {
      reject(new Error("Google Identity Services not loaded — try refreshing"));
      return;
    }
    const tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: S.CONFIG.googleClientId,
      scope: _PHOTOS_PICKER_SCOPE,
      callback: (tokenResponse) => {
        if (tokenResponse.error) {
          reject(new Error(tokenResponse.error_description || tokenResponse.error));
          return;
        }
        _googleOAuthToken = tokenResponse.access_token;
        resolve(_googleOAuthToken);
      },
    });
    tokenClient.requestAccessToken();
  });
}

/**
 * Create a Photos Picker session.
 * Returns { id, pickerUri, expireTime, mediaItemsSet }.
 */
export async function _createPickerSession(token) {
  const resp = await fetch(`${_PHOTOS_PICKER_API}/sessions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error?.message || `Failed to create picker session (${resp.status})`);
  }
  return resp.json();
}

/**
 * Poll a picker session until the user finishes picking (mediaItemsSet: true)
 * or the popup is closed.
 */
export function _pollPickerSession(sessionId, token) {
  return new Promise((resolve, reject) => {
    const poll = async () => {
      // If the popup was closed without picking, abort
      if (_pickerPopup && _pickerPopup.closed) {
        clearInterval(_pickerPollTimer);
        _pickerPollTimer = null;
        resolve(null); // null = user cancelled
        return;
      }

      try {
        const resp = await fetch(`${_PHOTOS_PICKER_API}/sessions/${sessionId}`, {
          headers: { "Authorization": `Bearer ${token}` },
        });
        if (!resp.ok) return; // retry on transient errors

        const session = await resp.json();
        if (session.mediaItemsSet) {
          clearInterval(_pickerPollTimer);
          _pickerPollTimer = null;
          if (_pickerPopup && !_pickerPopup.closed) _pickerPopup.close();
          resolve(session);
        }
      } catch (e) {
        // Network blip — keep polling
        console.warn("Picker poll error:", e);
      }
    };

    _pickerPollTimer = setInterval(poll, 2000);
    // Also do an immediate check
    poll();
  });
}

/**
 * Fetch the picked media items from a completed session.
 * Returns an array of { id, baseUrl, mimeType, createTime, ... }.
 */
export async function _getPickedMediaItems(sessionId, token) {
  const items = [];
  let pageToken = null;

  do {
    const url = new URL(`${_PHOTOS_PICKER_API}/sessions/${sessionId}/mediaItems`);
    if (pageToken) url.searchParams.set("pageToken", pageToken);

    const resp = await fetch(url.toString(), {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || `Failed to get media items (${resp.status})`);
    }

    const data = await resp.json();
    if (data.mediaItems) items.push(...data.mediaItems);
    pageToken = data.nextPageToken || null;
  } while (pageToken);

  return items;
}

/**
 * Open the Google Photos Picker.
 * Creates a session, opens the picker in a popup, polls for completion,
 * then downloads picked photos server-side.
 */
export async function openGooglePhotosPicker() {
  if (!S.PHOTO_PICKER_PERSON) return;
  const personId = S.PHOTO_PICKER_PERSON;

  const progressEl = document.getElementById("upload-progress");
  const progressText = document.getElementById("upload-progress-text");

  try {
    showToast("Connecting to Google Photos...");

    // 1. Get OAuth token
    const token = await _getPhotosPickerToken();

    // 2. Create picker session
    const session = await _createPickerSession(token);

    // 3. Open picker in popup
    const w = 1024, h = 700;
    const left = (screen.width - w) / 2;
    const top = (screen.height - h) / 2;
    _pickerPopup = window.open(
      session.pickerUri,
      "googlePhotosPicker",
      `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no`
    );

    if (!_pickerPopup) {
      showToast("Popup blocked — please allow popups for this site", "error");
      return;
    }

    showToast("Pick your photos in the Google Photos window...");

    // 4. Poll until user finishes
    const completed = await _pollPickerSession(session.id, token);
    if (!completed) {
      // User closed the popup without picking
      return;
    }

    // 5. Fetch picked media items
    if (progressEl) progressEl.classList.remove("hidden");
    if (progressText) progressText.textContent = "Fetching selected photos...";

    const mediaItems = await _getPickedMediaItems(session.id, token);
    if (mediaItems.length === 0) {
      showToast("No photos selected");
      return;
    }

    // 6. Build items for the server endpoint
    // The Photos Picker API returns mediaItems with:
    //   - mediaFile.baseUrl: the download URL (append =d for full size)
    //   - mediaFile.filename: original filename
    //   - mediaFile.mimeType: e.g. image/jpeg
    const items = mediaItems.map((mi) => {
      const mf = mi.mediaFile || {};
      let url = mf.baseUrl || "";
      // Append =d to get the full-resolution download
      if (url && !url.includes("=d")) url += "=d";
      const filename = mf.filename || mi.id || "google-photo.jpg";
      return { url, filename };
    }).filter((item) => item.url);

    if (items.length === 0) {
      showToast("Could not get download URLs for selected photos", "error");
      return;
    }

    if (progressText) progressText.textContent = `Importing ${items.length} photo${items.length > 1 ? "s" : ""} from Google Photos...`;

    // 7. Send to server for download
    const resp = await fetch(`/api/people/${personId}/google-photos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });
    const result = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      showToast(result.error || "Failed to import photos", "error");
      return;
    }

    // Update local caches. Newly imported photos need their full objects in
    // S.DATA.photos for the person_photos-derived views, so reload canonical
    // data before refreshing the picker/panel.
    if (S.ALL_PHOTOS && result.photo_paths) {
      for (const p of result.photo_paths) {
        if (!S.ALL_PHOTOS.includes(p)) S.ALL_PHOTOS.push(p);
      }
    }
    await loadData();
    _buildPickerGrid(personId);
    _renderPanelPhotos(personId);

    const msg = result.downloaded
      ? `${result.downloaded} photo${result.downloaded > 1 ? "s" : ""} imported from Google Photos`
      : "No photos imported";
    showToast(msg);

    if (result.errors && result.errors.length > 0) {
      console.warn("Google Photos import errors:", result.errors);
      showToast(`${result.errors.length} photo${result.errors.length > 1 ? "s" : ""} could not be imported`, "error");
    }
  } catch (err) {
    console.error("Google Photos Picker error:", err);
    showToast("Could not open Google Photos: " + err.message, "error");
  } finally {
    if (progressEl) progressEl.classList.add("hidden");
    if (_pickerPollTimer) {
      clearInterval(_pickerPollTimer);
      _pickerPollTimer = null;
    }
  }
}

// Wire up the Google Photos button
document.getElementById("google-photos-btn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  openGooglePhotosPicker();
});

// ═══════════════════════════════════════════════════════════════
// Hovercard
// ═══════════════════════════════════════════════════════════════

