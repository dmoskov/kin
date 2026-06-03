// Part of the family-tree web app (ES module).
// Shared mutable state lives in S (00-state.js); functions/consts are
// bridged onto window by 99-main.js so inline onclick handlers resolve.
import { S } from "./00-state.js";


export async function checkAuth() {
  try {
    const resp = await fetch("/api/auth/me");
    if (resp.ok) {
      S.AUTH_USER = await resp.json();
      return true;
    }
  } catch (_) {}
  S.AUTH_USER = null;
  return false;
}

/** Called by Google Sign-In when user signs in */
export async function handleGoogleSignIn(response) {
  try {
    const resp = await fetch("/api/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    const data = await resp.json();
    if (resp.ok) {
      // If we're on the login gate, reload the page to do a full init
      if (document.getElementById("login-gate")) {
        location.reload();
        return;
      }
      S.AUTH_USER = data;
      applyAuth();
      // Re-center on the authenticated person (only if they have a real person record)
      if (!data.person_id.startsWith("editor:")) {
        setCenterPerson(data.person_id);
      }
      refreshAllViews();
    } else {
      alert(data.error || "Login failed — no matching person record for your email.");
    }
  } catch (err) {
    console.error("Auth error:", err);
    alert("Sign-in failed. Please try again.");
  }
}

export async function handleLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (_) {}
  S.AUTH_USER = null;
  applyAuth();
}

