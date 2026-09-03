// Panah — auth.js
// Real Firebase Phone Auth implementation.
//
// Flow:
//   1. User enters phone number -> signInWithPhoneNumber() sends the code
//      (or, for whitelisted test numbers, Firebase skips the real SMS and
//      just accepts the hardcoded test OTP you set in the console).
//   2. User enters the code -> confirmationResult.confirm(code) verifies it
//      with Firebase directly (this app never sees or checks the code itself).
//   3. On success, we get a Firebase ID token and send it to our OWN backend
//      (/verify-session) so Flask can confirm it server-side and create/find
//      the user record. Only after the backend confirms do we set the
//      logged-in flag and redirect.

/* ===================================================================
   1. CONFIG — fill these in from Firebase Console > Project settings >
      General > Your apps > Web app (the values shown when you register
      a web app in step 4 of console setup).
   =================================================================== */

const FIREBASE_CONFIG = {
  apiKey: "AIzaSyDoyX59MXO6I_pBpgoe1hfRrNHDsrLQM-8",
  authDomain: "panah-a1e41.firebaseapp.com",
  projectId: "panah-a1e41",
  storageBucket: "panah-a1e41.firebasestorage.app",
  messagingSenderId: "362734433731",
  appId: "1:362734433731:web:9746268a74eef65a073976",
};

/** Backend base URL — same one script.js uses for /ask. */
const AUTH_API_BASE = "http://127.0.0.1:5000";

/** localStorage keys — must match the ones script.js reads. */
const LS_LOGIN_FLAG = "panah_logged_in";
const LS_USER_LABEL = "panah_user_label";

firebase.initializeApp(FIREBASE_CONFIG);
const auth = firebase.auth();
auth.useEmulator("http://127.0.0.1:9099");

/* ===================================================================
   2. DOM REFERENCES
   =================================================================== */

const phoneForm       = document.getElementById("phone-form");
const phoneInput      = document.getElementById("phone-input");
const sendCodeBtn     = document.getElementById("send-code-btn");

const otpForm         = document.getElementById("otp-form");
const otpInput        = document.getElementById("otp-input");
const verifyCodeBtn   = document.getElementById("verify-code-btn");
const otpSentToNote   = document.getElementById("otp-sent-to-note");
const changeNumberBtn = document.getElementById("change-number-btn");

const errorNote       = document.getElementById("auth-error");

/* ===================================================================
   3. STATE
   =================================================================== */

/** Set once signInWithPhoneNumber() succeeds; used to verify the code. */
let confirmationResult = null;

/** The full E.164 number ("+923001234567") the code was sent to. */
let pendingPhoneNumber = null;

/* ===================================================================
   4. HELPERS
   =================================================================== */

function showError(message) {
  errorNote.textContent = message;
  errorNote.hidden = false;
}

function clearError() {
  errorNote.hidden = true;
  errorNote.textContent = "";
}

function setButtonBusy(button, busy, busyLabel, idleLabel) {
  button.disabled = busy;
  button.textContent = busy ? busyLabel : idleLabel;
}

/** Turns whatever digits the user typed into +92XXXXXXXXXX, or null if invalid. */
function toE164(rawDigits) {
  const digits = rawDigits.replace(/\D/g, "");
  // Expect a 10-digit local number like 3001234567 (leading 0 optional/stripped).
  const trimmed = digits.startsWith("0") ? digits.slice(1) : digits;
  if (trimmed.length !== 10) return null;
  return `+92${trimmed}`;
}

/* ===================================================================
   5. reCAPTCHA — required by Firebase before it will send an SMS,
      even for whitelisted test numbers.
   =================================================================== */

function ensureRecaptcha() {
  if (window.recaptchaVerifier) return window.recaptchaVerifier;

  window.recaptchaVerifier = new firebase.auth.RecaptchaVerifier(
    "recaptcha-container",
    { size: "invisible" }
  );
  return window.recaptchaVerifier;
}

/* ===================================================================
   6. STEP 1 — send the code
   =================================================================== */

phoneForm.addEventListener("submit", async function (e) {
  e.preventDefault();
  clearError();

  const phoneNumber = toE164(phoneInput.value);
  if (!phoneNumber) {
    showError("Mobile number lagta hai adhoora hai — 10 digit number likhein (e.g. 3001234567).");
    return;
  }

  setButtonBusy(sendCodeBtn, true, "Sending…", "Send code");

  try {
    const appVerifier = ensureRecaptcha();
    confirmationResult = await auth.signInWithPhoneNumber(phoneNumber, appVerifier);
    pendingPhoneNumber = phoneNumber;

    otpSentToNote.textContent = `Code sent to ${phoneNumber}`;
    phoneForm.hidden = true;
    otpForm.hidden = false;
    otpInput.focus();
  } catch (err) {
    console.error("signInWithPhoneNumber failed:", err);
    // Reset the invisible reCAPTCHA widget so the user can retry cleanly.
    if (window.recaptchaVerifier) {
      window.recaptchaVerifier.render().then((widgetId) => {
        if (window.grecaptcha) window.grecaptcha.reset(widgetId);
      });
    }
    showError("Code bhejne mein masla hua. Number check karke dobara koshish karein.");
  } finally {
    setButtonBusy(sendCodeBtn, false, "Sending…", "Send code");
  }
});

/* ===================================================================
   7. STEP 2 — verify the code, then confirm with OUR backend
   =================================================================== */

otpForm.addEventListener("submit", async function (e) {
  e.preventDefault();
  clearError();

  const code = otpInput.value.trim();
  if (!code || code.length < 4) {
    showError("6-digit code likhein.");
    return;
  }
  if (!confirmationResult) {
    showError("Session expire ho gaya. Number dobara submit karein.");
    return;
  }

  setButtonBusy(verifyCodeBtn, true, "Verifying…", "Verify & continue");

  try {
    const userCredential = await confirmationResult.confirm(code);
    const idToken = await userCredential.user.getIdToken();

    // Firebase confirms the phone is real. Now our own backend checks that
    // token server-side and creates/finds the user record before we treat
    // this as a real login.
    const response = await fetch(`${AUTH_API_BASE}/verify-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken }),
    });

    if (!response.ok) {
      throw new Error(`Backend rejected session (status ${response.status})`);
    }

    const data = await response.json();

    localStorage.setItem(LS_LOGIN_FLAG, "1");
    localStorage.setItem(LS_USER_LABEL, data.phone || pendingPhoneNumber);

    window.location.href = "homepage.html";
  } catch (err) {
    console.error("OTP verification failed:", err);
    showError("Code sahi nahi hai ya expire ho gaya. Dobara koshish karein.");
  } finally {
    setButtonBusy(verifyCodeBtn, false, "Verifying…", "Verify & continue");
  }
});

/* ===================================================================
   8. "Use a different number" — resets back to step 1
   =================================================================== */

changeNumberBtn.addEventListener("click", function () {
  clearError();
  confirmationResult = null;
  pendingPhoneNumber = null;
  otpInput.value = "";
  otpForm.hidden = true;
  phoneForm.hidden = false;
  phoneInput.focus();
});