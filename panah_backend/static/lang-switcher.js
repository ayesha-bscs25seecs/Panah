/**
 * Panah — lang-switcher.js
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 * Persistent language selector dropdown for the navbar.
 *
 * Renders a button next to the Panah logo showing the currently active
 * language (ur → "اردو", en → "EN", roman → "Roman"). Clicking it
 * toggles a dropdown with three options. Selecting a language:
 *   1. Calls PanahI18n.setLang() to persist in localStorage ("panah_lang")
 *   2. Calls PanahI18n.applyLanguage() to re-translate all data-i18n elements
 *   3. Updates the button label and active state in the dropdown
 *
 * Requires: i18n.js (PanahI18n) loaded BEFORE this script.
 *
 * NOTE: This does NOT replace or modify the first-visit entry modal in
 * entry.js — it coexists with it. The modal sets the initial language;
 * this switcher lets the user change it any time afterwards.
 */

(function () {
  "use strict";

  /**
   * Initialize the language switcher. Called immediately if the DOM is ready,
   * or deferred to DOMContentLoaded if this script is loaded before <body>
   * has been parsed.
   */
  function init() {

  /* ===================================================================
     CONFIG — human-readable labels for each language option.
     These are intentionally NOT translated (language names are universal).
     =================================================================== */
  var LANG_LABELS = {
    ur:    "\u0627\u0631\u062F\u0648",   // اردو
    en:    "English",
    roman: "Roman Urdu",
  };

  /** Short labels shown on the compact navbar button. */
  var LANG_SHORT = {
    ur:    "\u0627\u0631\u062F\u0648",   // اردو
    en:    "EN",
    roman: "Roman",
  };

  /** CSS class for the expanded (open) state of the dropdown. */
  var OPEN_CLASS = "lang-switcher-open";

  /* ===================================================================
     DOM REFERENCES — guarded; exits silently if elements aren't present
     (e.g. on pages that don't include the switcher markup).
     =================================================================== */
  var switcher  = document.getElementById("lang-switcher");
  var btn       = document.getElementById("lang-switcher-btn");
  var dropdown  = document.getElementById("lang-switcher-dropdown");
  var labelSpan = document.getElementById("lang-switcher-label");

  if (!switcher || !btn || !dropdown || !labelSpan) return;
  if (!window.PanahI18n) return;

  /* ===================================================================
     HELPERS
     =================================================================== */

  /** Updates the button text to reflect the currently active language. */
  function updateButtonLabel() {
    var currentLang = window.PanahI18n.getLang();
    labelSpan.textContent = LANG_SHORT[currentLang] || currentLang;
  }

  /** Highlights the active language option in the dropdown. */
  function updateActiveOption() {
    var currentLang = window.PanahI18n.getLang();
    var options = dropdown.querySelectorAll("[data-lang]");
    for (var i = 0; i < options.length; i++) {
      var opt = options[i];
      if (opt.getAttribute("data-lang") === currentLang) {
        opt.classList.add("active");
      } else {
        opt.classList.remove("active");
      }
    }
  }

  /** Opens or closes the dropdown. */
  function toggleDropdown(e) {
    e.stopPropagation();
    switcher.classList.toggle(OPEN_CLASS);
    var isOpen = switcher.classList.contains(OPEN_CLASS);
    btn.setAttribute("aria-expanded", String(isOpen));
  }

  /** Closes the dropdown (used for outside-click and Escape). */
  function closeDropdown() {
    switcher.classList.remove(OPEN_CLASS);
    btn.setAttribute("aria-expanded", "false");
  }

  /**
   * Handles a language selection:
   *  1. Persist via PanahI18n.setLang()  (writes localStorage "panah_lang")
   *  2. Re-translate the page via PanahI18n.applyLanguage()
   *  3. Update the switcher UI (label + active option)
   *  4. Close the dropdown
   */
  function selectLanguage(lang) {
    window.PanahI18n.setLang(lang);
    window.PanahI18n.applyLanguage(lang);

    updateButtonLabel();
    updateActiveOption();
    closeDropdown();
  }

  /* ===================================================================
     EVENT BINDING
     =================================================================== */

  // Toggle dropdown on button click
  btn.addEventListener("click", toggleDropdown);

  // Delegate clicks on language options
  dropdown.addEventListener("click", function (e) {
    var option = e.target.closest("[data-lang]");
    if (option) {
      selectLanguage(option.getAttribute("data-lang"));
    }
  });

  // Close when clicking outside the switcher
  document.addEventListener("click", function (e) {
    if (!switcher.contains(e.target)) {
      closeDropdown();
    }
  });

  // Close on Escape key for accessibility
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeDropdown();
    }
  });

  // Set the initial label and active state from localStorage
  updateButtonLabel();
  updateActiveOption();

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
