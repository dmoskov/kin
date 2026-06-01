// Part of the family-tree web app. Loaded as an ordered classic script.
// See index.html for load order. Split from the former monolithic app.js.

let AUTH_USER = null; // { person_id, name, email } or null

async function checkAuth() {
  try {
    const resp = await fetch("/api/auth/me");
    if (resp.ok) {
      AUTH_USER = await resp.json();
      return true;
    }
  } catch (_) {}
  AUTH_USER = null;
  return false;
}

/** Called by Google Sign-In when user signs in */
async function handleGoogleSignIn(response) {
  try {
    const resp = await fetch("/api/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    const data = await resp.json();
    if (resp.ok) {
      AUTH_USER = data;
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

async function handleLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (_) {}
  AUTH_USER = null;
  applyAuth();
}

