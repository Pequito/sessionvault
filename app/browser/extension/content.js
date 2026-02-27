/**
 * SessionVault – content script.
 *
 * Injected into every page.  Responsibilities:
 *   1. Detect login forms (password inputs).
 *   2. Inject a small fill-button (🔑) next to each password field.
 *   3. Listen for "svFill" messages from the background service worker and
 *      actually fill the form fields.
 *
 * The content script never talks to localhost directly – all API calls go
 * through background.js so that credentials are not exposed to page scripts.
 */

(function () {
  "use strict";

  // Guard: don't run twice in the same document
  if (window.__sessionvaultLoaded) return;
  window.__sessionvaultLoaded = true;

  // -------------------------------------------------------------------------
  // Utilities
  // -------------------------------------------------------------------------

  /** Dispatch synthetic events so the host page's validators recognise the fill. */
  function triggerEvents(input) {
    ["input", "change", "keydown", "keyup", "keypress"].forEach((type) => {
      input.dispatchEvent(new Event(type, { bubbles: true }));
    });
  }

  /**
   * Guess the username / email input associated with a password field.
   * Walks backwards through sibling / ancestor inputs looking for text-like
   * fields (type=text, email, tel, or name containing "user"/"login"/"email").
   */
  function findUsernameInput(passwordInput) {
    const form = passwordInput.form;
    const candidates = form
      ? Array.from(form.elements)
      : Array.from(
          (passwordInput.closest("div, section, main, body") || document.body)
            .querySelectorAll("input")
        );

    const textTypes = new Set(["text", "email", "tel", ""]);
    const namePat   = /user|login|email|account|id/i;

    // Find all text-like inputs that appear before the password field
    const before = [];
    for (const el of candidates) {
      if (el === passwordInput) break;
      if (el.tagName === "INPUT" && textTypes.has(el.type)) {
        before.push(el);
      }
    }

    if (!before.length) return null;

    // Prefer one whose name/id/placeholder matches the pattern
    const preferred = before
      .slice()
      .reverse()
      .find((el) =>
        namePat.test(el.name) ||
        namePat.test(el.id) ||
        namePat.test(el.placeholder)
      );
    // Otherwise take the closest preceding text input
    return preferred ?? before[before.length - 1];
  }

  // -------------------------------------------------------------------------
  // Inject fill buttons
  // -------------------------------------------------------------------------

  const BUTTON_ID = "sv-fill-btn";

  function injectFillButtons() {
    document.querySelectorAll(`input[type="password"]`).forEach((pwInput) => {
      if (pwInput.dataset.svInjected) return;
      pwInput.dataset.svInjected = "1";

      const btn = document.createElement("button");
      btn.type        = "button";
      btn.textContent = "🔑";
      btn.title       = "Fill from SessionVault";
      btn.setAttribute("aria-label", "Fill from SessionVault");

      // Inline styles – small, unobtrusive, overlaid at the right edge of the input
      Object.assign(btn.style, {
        position:    "absolute",
        right:       "6px",
        top:         "50%",
        transform:   "translateY(-50%)",
        zIndex:      "2147483647",
        background:  "transparent",
        border:      "none",
        cursor:      "pointer",
        fontSize:    "16px",
        padding:     "0",
        lineHeight:  "1",
      });

      // Wrap input in a positioned container so absolute positioning works
      const wrapper = document.createElement("span");
      Object.assign(wrapper.style, {
        position: "relative",
        display:  "inline-block",
      });
      pwInput.parentNode.insertBefore(wrapper, pwInput);
      wrapper.appendChild(pwInput);
      wrapper.appendChild(btn);

      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        requestFill(pwInput);
      });
    });
  }

  /**
   * Ask the background worker for logins for the current page and fill the
   * form the clicked password field belongs to.
   */
  function requestFill(pwInput) {
    chrome.runtime.sendMessage(
      { action: "getLogins", url: window.location.href },
      (response) => {
        if (!response?.ok || !response.entries?.length) {
          showInlineStatus(
            pwInput,
            response?.dbLocked
              ? "SessionVault: database is locked"
              : "SessionVault: no matching credentials found",
            "warning"
          );
          return;
        }
        if (response.entries.length === 1) {
          fillForm(pwInput, response.entries[0]);
        } else {
          showPicker(pwInput, response.entries);
        }
      }
    );
  }

  // -------------------------------------------------------------------------
  // Inline picker (multiple matches)
  // -------------------------------------------------------------------------

  function showPicker(pwInput, entries) {
    removePicker();
    const picker = document.createElement("div");
    picker.id = "sv-picker";
    Object.assign(picker.style, {
      position:        "fixed",
      zIndex:          "2147483647",
      background:      "#1e1e2e",
      border:          "1px solid #cba6f7",
      borderRadius:    "8px",
      boxShadow:       "0 8px 24px rgba(0,0,0,0.6)",
      padding:         "8px 0",
      minWidth:        "260px",
      fontFamily:      "system-ui, sans-serif",
      fontSize:        "13px",
      color:           "#cdd6f4",
    });

    // Position near the input
    const rect = pwInput.getBoundingClientRect();
    picker.style.top  = `${Math.min(rect.bottom + 4, window.innerHeight - 200)}px`;
    picker.style.left = `${Math.max(rect.left, 4)}px`;

    // Header
    const hdr = document.createElement("div");
    hdr.textContent = "SessionVault – select credential";
    Object.assign(hdr.style, {
      padding:     "4px 12px 8px",
      fontSize:    "11px",
      color:       "#a6adc8",
      borderBottom:"1px solid #313244",
      marginBottom:"4px",
    });
    picker.appendChild(hdr);

    entries.forEach((entry) => {
      const row = document.createElement("button");
      row.type = "button";
      Object.assign(row.style, {
        display:     "block",
        width:       "100%",
        padding:     "7px 12px",
        background:  "transparent",
        border:      "none",
        cursor:      "pointer",
        textAlign:   "left",
        color:       "#cdd6f4",
      });
      row.innerHTML = `
        <span style="font-weight:600">${esc(entry.title || "(no title)")}</span>
        <span style="color:#a6adc8;margin-left:8px">${esc(entry.username || "")}</span>
      `;
      row.addEventListener("mouseover", () => { row.style.background = "#313244"; });
      row.addEventListener("mouseout",  () => { row.style.background = "transparent"; });
      row.addEventListener("click", () => {
        removePicker();
        fillForm(pwInput, entry);
      });
      picker.appendChild(row);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") removePicker();
    }, { once: true });
    document.addEventListener("click", () => removePicker(), { once: true });

    document.body.appendChild(picker);
  }

  function removePicker() {
    document.getElementById("sv-picker")?.remove();
  }

  // -------------------------------------------------------------------------
  // Form filling
  // -------------------------------------------------------------------------

  function fillForm(pwInput, entry) {
    const usernameInput = findUsernameInput(pwInput);
    if (usernameInput && entry.username) {
      usernameInput.value = entry.username;
      triggerEvents(usernameInput);
    }
    if (entry.password) {
      pwInput.value = entry.password;
      triggerEvents(pwInput);
    }
  }

  // -------------------------------------------------------------------------
  // Status toast
  // -------------------------------------------------------------------------

  function showInlineStatus(anchor, msg, type) {
    const id = "sv-status-toast";
    document.getElementById(id)?.remove();
    const toast = document.createElement("div");
    toast.id = id;
    toast.textContent = msg;
    const bg = type === "warning" ? "#f38ba8" : "#a6e3a1";
    Object.assign(toast.style, {
      position:    "fixed",
      zIndex:      "2147483647",
      background:  bg,
      color:       "#1e1e2e",
      padding:     "6px 14px",
      borderRadius:"6px",
      fontSize:    "12px",
      fontFamily:  "system-ui, sans-serif",
      boxShadow:   "0 4px 12px rgba(0,0,0,0.4)",
      bottom:      "20px",
      right:       "20px",
    });
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  // -------------------------------------------------------------------------
  // Receive fill message from background / popup
  // -------------------------------------------------------------------------

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action !== "svFill") return;
    const pwInputs = document.querySelectorAll(`input[type="password"]:not([disabled])`);
    if (!pwInputs.length) return;
    fillForm(pwInputs[0], msg);
  });

  // -------------------------------------------------------------------------
  // Observe DOM for dynamically added login forms (SPAs)
  // -------------------------------------------------------------------------

  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Initial scan
  injectFillButtons();

  // Watch for new password fields added by JavaScript frameworks
  const observer = new MutationObserver(() => injectFillButtons());
  observer.observe(document.body, { childList: true, subtree: true });
})();
