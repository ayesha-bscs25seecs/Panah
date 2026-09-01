// Panah — auth.js
// STUB VERSION: no real OTP verification yet.
//
// TODO (when ready to wire in real auth):
//   1. Add Firebase JS SDK <script> tags to auth.html
//   2. On phone submit -> firebase.auth().signInWithPhoneNumber(...)
//   3. On OTP submit    -> confirmationResult.confirm(code)
//   4. On success, send the Firebase ID token to a new Flask route
//      (e.g. POST /verify-session), verify it server-side with
//      firebase_admin.auth.verify_id_token(), then create/match the
//      user record by phone number and set your own session cookie.
//   5. Only THEN redirect to homepage.html — remove the unconditional
//      redirect below.

document.getElementById('auth-form').addEventListener('submit', function (e) {
  e.preventDefault();

  // NOTE: intentionally not reading/validating phone-input or otp-input
  // values here yet — this is a flow stub only.

  window.location.href = 'homepage.html';
});
