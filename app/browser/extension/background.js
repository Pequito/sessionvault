/**
 * SessionVault – background service worker.
 *
 * Acts as the single point of contact for both the popup and content scripts.
 * All communication with the SessionVault local HTTP server
 * (http://127.0.0.1:19456) goes through here so the server URL is never
 * embedded in content scripts that run inside untrusted pages.
 *
 * Message protocol (chrome.runtime.sendMessage)
 * ─────────────────────────────────────────────
 * { action: "ping" }
 *   → { ok: bool, dbOpen: bool, dbCount: int, version: string }
 *
 * { action: "getLogins", url: string }
 *   → { ok: bool, entries: Entry[], error?: string }
 *
 * { action: "saveLogin", url, title, username, password }
 *   → { ok: bool, success: bool }
 *
 * { action: "updateLogin", uuid, username, password, url, title }
 *   → { ok: bool, success: bool }
 *
 * { action: "fillCredentials", tabId: int, username: string, password: string }
 *   → (injects fill message into the tab's content script; no response)
 */

const SV_BASE = "http://127.0.0.1:19456";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiGet(path) {
  const res = await fetch(`${SV_BASE}${path}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${SV_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Message router
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  handleMessage(msg)
    .then(sendResponse)
    .catch((err) => sendResponse({ ok: false, error: String(err) }));
  return true; // keep message channel open for async response
});

async function handleMessage(msg) {
  switch (msg.action) {
    case "ping": {
      try {
        const data = await apiGet("/ping");
        return { ok: true, dbOpen: data.dbOpen, dbCount: data.dbCount, version: data.version };
      } catch {
        return { ok: false, dbOpen: false, error: "SessionVault not running" };
      }
    }

    case "getLogins": {
      if (!msg.url) return { ok: false, error: "url_required", entries: [] };
      try {
        const data = await apiPost("/get-logins", { url: msg.url });
        if (data.error === "no_database_open") {
          return { ok: true, entries: [], dbLocked: true };
        }
        return { ok: true, entries: data.entries ?? [] };
      } catch {
        return { ok: false, entries: [], error: "SessionVault not running" };
      }
    }

    case "saveLogin": {
      try {
        const data = await apiPost("/save-login", {
          url:      msg.url      ?? "",
          title:    msg.title    ?? "",
          username: msg.username ?? "",
          password: msg.password ?? "",
        });
        return { ok: true, success: data.success };
      } catch (err) {
        return { ok: false, success: false, error: String(err) };
      }
    }

    case "updateLogin": {
      try {
        const data = await apiPost("/update-login", {
          uuid:     msg.uuid     ?? "",
          username: msg.username,
          password: msg.password,
          url:      msg.url,
          title:    msg.title,
        });
        return { ok: true, success: data.success };
      } catch (err) {
        return { ok: false, success: false, error: String(err) };
      }
    }

    case "fillCredentials": {
      // Forward fill payload to the content script in the given tab
      if (msg.tabId == null) return { ok: false, error: "tabId_required" };
      await chrome.tabs.sendMessage(msg.tabId, {
        action:   "svFill",
        username: msg.username ?? "",
        password: msg.password ?? "",
      });
      return { ok: true };
    }

    default:
      return { ok: false, error: `unknown_action: ${msg.action}` };
  }
}
