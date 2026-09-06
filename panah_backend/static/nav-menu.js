/**
 * Panah — nav-menu.js
 * ~~~~~~~~~~~~~~~~~~~
 * Mobile hamburger menu for the shared landing header.
 *
 * Below 768px (see the MOBILE NAV section in landing.css) the six nav links
 * collapse into a hamburger button on the right of the header, and the
 * .landing-nav element itself becomes the slide-down panel. This script
 * toggles the .nav-open class on it and keeps the button's aria-expanded
 * in sync. Above 768px the button is display:none and nothing runs that
 * would affect the desktop bar.
 *
 * The menu closes when:
 *   - the hamburger is clicked again
 *   - a link inside the open panel is clicked (navigation continues)
 *   - the user clicks anywhere outside the nav/button (e.g. the logo or
 *     the language switcher — mirroring lang-switcher.js)
 *   - Escape is pressed
 *   - the viewport grows past the mobile breakpoint
 *
 * Requires: nothing (plain progressive enhancement; safe on pages without
 * the header markup).
 */

(function () {
  "use strict";

  /**
   * Initialize the hamburger menu. Called immediately if the DOM is ready,
   * or deferred to DOMContentLoaded if this script is loaded before <body>
   * has been parsed.
   */
  function init() {

  /* ===================================================================
     CONFIG — CSS class for the open (slide-down) state of the panel.
     Keep in sync with landing.css and the breakpoint below.
     =================================================================== */
  var OPEN_CLASS  = "nav-open";
  var DESKTOP_MQ  = window.matchMedia("(min-width: 769px)");

  /* ===================================================================
     DOM REFERENCES — guarded; exits silently on pages that don't include
     the header markup (e.g. the chat page).
     =================================================================== */
  var nav = document.getElementById("landing-nav");
  var btn = document.getElementById("nav-toggle-btn");

  if (!nav || !btn) return;

  /* ===================================================================
     STATE HELPERS
     =================================================================== */

  function isOpen() {
    return nav.classList.contains(OPEN_CLASS);
  }

  function openMenu() {
    nav.classList.add(OPEN_CLASS);
    btn.setAttribute("aria-expanded", "true");
  }

  function closeMenu() {
    nav.classList.remove(OPEN_CLASS);
    btn.setAttribute("aria-expanded", "false");
  }

  /* ===================================================================
     EVENT BINDING
     =================================================================== */

  // Toggle the panel on hamburger click
  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    if (isOpen()) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  // Choosing a link closes the panel (navigation continues normally)
  nav.addEventListener("click", function (e) {
    if (e.target.closest("a") && isOpen()) {
      closeMenu();
    }
  });

  // Close when clicking outside the nav panel / hamburger — same pattern
  // as the language switcher, so opening one dismisses the other. Registered
  // in the CAPTURE phase because the lang-switcher button's own handler
  // calls e.stopPropagation(), which would otherwise hide its clicks from
  // a bubble-phase listener on document.
  document.addEventListener("click", function (e) {
    if (isOpen() && !nav.contains(e.target) && !btn.contains(e.target)) {
      closeMenu();
    }
  }, true);

  // Close on Escape key for accessibility
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isOpen()) {
      closeMenu();
    }
  });

  // Close if the viewport grows past the mobile breakpoint, so the bar
  // never returns to desktop with a stale .nav-open state.
  function onDesktop(e) {
    if (e.matches) closeMenu();
  }
  if (DESKTOP_MQ.addEventListener) {
    DESKTOP_MQ.addEventListener("change", onDesktop);
  } else if (DESKTOP_MQ.addListener) {
    DESKTOP_MQ.addListener(onDesktop); // older browsers
  }

  } // end init()

  /* ===================================================================
     BOOTSTRAP — defer to DOMContentLoaded if loaded before <body> has
     been parsed.
     =================================================================== */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
