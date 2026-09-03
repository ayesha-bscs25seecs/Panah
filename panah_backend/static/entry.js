/**
 * Panah — entry.js
 * Sequential entry popups shown on first visit to the homepage:
 *   1. Language selection
 *   2. Login vs. continue-as-guest
 *
 * Choices are persisted in localStorage so the user is not asked again
 * on every page navigation.
 */

(function () {
  const LS_ENTRY_CHOICE = "panah_entry_choice";

  const overlay = document.getElementById("entry-overlay");
  const langModal = document.getElementById("lang-modal");
  const entryModal = document.getElementById("entry-modal");

  if (!overlay || !langModal || !entryModal) return;

  function showLanguageModal() {
    overlay.hidden = false;
    langModal.hidden = false;
    entryModal.hidden = true;
  }

  function showEntryModal() {
    overlay.hidden = false;
    langModal.hidden = true;
    entryModal.hidden = false;
  }

  function hideAll() {
    overlay.hidden = true;
    langModal.hidden = true;
    entryModal.hidden = true;
  }

  function chooseLanguage(lang) {
    if (window.PanahI18n) {
      window.PanahI18n.setLang(lang);
      window.PanahI18n.applyLanguage(lang);
    }
    showEntryModal();
  }

  document.querySelectorAll("[data-lang-select]").forEach((btn) => {
    btn.addEventListener("click", () => chooseLanguage(btn.dataset.langSelect));
  });

  document.getElementById("lang-skip")?.addEventListener("click", () => {
    chooseLanguage("ur");
  });

  document.getElementById("entry-login")?.addEventListener("click", () => {
    localStorage.setItem(LS_ENTRY_CHOICE, "login");
    window.location.href = "auth.html";
  });

  document.getElementById("entry-guest")?.addEventListener("click", () => {
    localStorage.setItem(LS_ENTRY_CHOICE, "guest");
    hideAll();
  });

  const hasLang = !!localStorage.getItem("panah_lang");
  const hasEntry = !!localStorage.getItem(LS_ENTRY_CHOICE);

  if (!hasLang) {
    showLanguageModal();
  } else if (!hasEntry) {
    if (window.PanahI18n) window.PanahI18n.applyLanguage();
    showEntryModal();
  } else {
    if (window.PanahI18n) window.PanahI18n.applyLanguage();
    hideAll();
  }
})();
