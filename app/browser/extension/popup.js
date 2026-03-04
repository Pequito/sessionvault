/**
 * SessionVault – popup script.
 *
 * Orchestrates the popup UI:
 *   1. On open: ping SessionVault, then fetch credentials for the current tab.
 *   2. Render the entry list with Fill and Copy buttons.
 *   3. Handle "Save login" form.
 *   4. Delegate fill / save / update to background.js via sendMessage.
 */

"use strict";

// ── DOM refs ──────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const panels = {
  loading: $("panel-loading"),
  offline:  $("panel-offline"),
  locked:   $("panel-locked"),
  creds:    $("panel-creds"),
};

const footer       = $("footer");
const entriesList  = $("entries-list");
const noMatch      = $("no-match");
const saveForm     = $("save-form");
const feedbackEl   = $("feedback");
const statusDot    = $("status-dot");

// ── State ─────────────────────────────────────────────────────────────────

let currentTab   = null;
let currentEntries = [];

// ── Boot ──────────────────────────────────────────────────────────────────

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tab;
  await loadCredentials();
})();

// ── Load credentials for current tab ─────────────────────────────────────

async function loadCredentials() {
  showPanel("loading");
  footer.style.display = "none";

  const ping = await bg({ action: "ping" });
  if (!ping.ok) {
    statusDot.className = "disconnected";
    statusDot.title = "SessionVault not running";
    showPanel("offline");
    return;
  }

  if (!ping.dbOpen) {
    statusDot.className = "locked";
    statusDot.title = "Database locked";
    showPanel("locked");
    footer.style.display = "flex";
    return;
  }

  statusDot.className = "connected";
  statusDot.title = `Connected – ${ping.dbCount ?? 1} database(s) open`;

  const url = currentTab?.url ?? "";
  const result = await bg({ action: "getLogins", url });

  currentEntries = result.entries ?? [];
  renderEntries(currentEntries);
  showPanel("creds");
  footer.style.display = "flex";
}

// ── Render entry rows ─────────────────────────────────────────────────────

function renderEntries(entries) {
  entriesList.innerHTML = "";
  noMatch.style.display = entries.length ? "none" : "";

  entries.forEach((entry) => {
    const li = document.createElement("li");

    const info = document.createElement("div");
    info.className = "entry-info";
    info.innerHTML = `
      <div class="entry-title">${esc(entry.title || "(no title)")}</div>
      <div class="entry-user">${esc(entry.username || "")}</div>
    `;
    li.appendChild(info);

    // Fill button
    const fillBtn = document.createElement("button");
    fillBtn.className = "btn btn-fill";
    fillBtn.textContent = "Fill";
    fillBtn.title = "Fill username + password on the page";
    fillBtn.addEventListener("click", () => fillEntry(entry));
    li.appendChild(fillBtn);

    // Copy password button
    const copyBtn = document.createElement("button");
    copyBtn.className = "btn btn-copy";
    copyBtn.textContent = "⎘ Pw";
    copyBtn.title = "Copy password to clipboard";
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(entry.password ?? "");
      flash(copyBtn, "Copied!");
    });
    li.appendChild(copyBtn);

    entriesList.appendChild(li);
  });
}

// ── Fill ──────────────────────────────────────────────────────────────────

async function fillEntry(entry) {
  if (!currentTab) return;
  await bg({
    action:   "fillCredentials",
    tabId:    currentTab.id,
    username: entry.username,
    password: entry.password,
  });
  window.close();
}

// ── Save form ─────────────────────────────────────────────────────────────

$("btn-show-save").addEventListener("click", () => {
  saveForm.classList.toggle("visible");
  if (saveForm.classList.contains("visible")) {
    // Pre-fill title from current tab hostname
    try {
      const host = new URL(currentTab?.url ?? "").hostname;
      $("save-title").value    = host;
    } catch {/* */}
  }
});

$("btn-cancel-save").addEventListener("click", () => {
  saveForm.classList.remove("visible");
  clearFeedback();
});

$("btn-do-save").addEventListener("click", async () => {
  const title    = $("save-title").value.trim();
  const username = $("save-username").value;
  const password = $("save-password").value;
  if (!title) { showFeedback("Title is required.", "err"); return; }

  const res = await bg({
    action:   "saveLogin",
    url:      currentTab?.url ?? "",
    title,
    username,
    password,
  });

  if (res.ok && res.success) {
    showFeedback("Login saved!", "ok");
    saveForm.classList.remove("visible");
    await loadCredentials();
  } else {
    showFeedback("Could not save – is a database open?", "err");
  }
});

// ── Refresh button ────────────────────────────────────────────────────────

$("btn-refresh").addEventListener("click", loadCredentials);

// ── Helpers ───────────────────────────────────────────────────────────────

function showPanel(name) {
  Object.entries(panels).forEach(([k, el]) => {
    el.classList.toggle("visible", k === name);
  });
}

function bg(msg) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(msg, (resp) =>
      resolve(resp ?? { ok: false, error: "no_response" })
    );
  });
}

function flash(btn, text) {
  const orig = btn.textContent;
  btn.textContent = text;
  setTimeout(() => { btn.textContent = orig; }, 1200);
}

function showFeedback(msg, type) {
  feedbackEl.textContent = msg;
  feedbackEl.className = `feedback ${type}`;
  feedbackEl.style.display = "";
}

function clearFeedback() {
  feedbackEl.style.display = "none";
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
