# Auth0 signup setup

The application sends `screen_hint=signup` to Auth0 Universal Login. Auth0 owns
the password, confirm-password field, email delivery, and database password
policy. Do not send the confirm value as an `ulp-*` field or save it in user
metadata.

1. Enable a password-capable Auth0 database connection for the application,
   while retaining the existing Google SSO and email OTP connections. Use New
   Universal Login. Confirm the tenant's authentication profile and available
   signup prompts before applying a partial.
2. Set the database connection's **Flexible Password Policy** to a minimum of
   eight characters with uppercase, number, and special-character requirements.
   The legacy `Good` policy is insufficient: it requires only three of four
   character classes. Auth0 must enforce the policy on the server, including
   password reset.
3. Add `signup-password-partial.html` to the password-entry signup prompt's
   `form-content-end` slot. For a single-screen signup profile, use the `signup`
   prompt; for identifier-first, use `signup-password`. The partial adds a
   client-only confirm field without a `name` attribute. Preview the actual
   tenant prompt and check that the validation function finds the Auth0
   password input. Its first selector expects `name="password"`; its fallback
   expects `autocomplete="new-password"`.
   Auth0 requires a custom domain and page template for prompt partials.
4. Enable the database connection's verification email template and an email
   provider that delivers to real addresses. Send the verification link after
   signup; set its redirect to the app landing page. Keep `email_verified=false`
   until Auth0 verifies the link. The app rejects ID tokens without
   `email_verified=true`, so a user must sign in again after verification.
5. Test with a new address: reject each invalid password class and a mismatch;
   accept a matching valid password; verify that email arrives; confirm its
   link; sign in again and reach the planner without admin action. For an
   existing OTP/password account, sign in with that account, choose **Link
   Google SSO**, complete a fresh Google sign-in, then sign out and return with
   Google. Confirm the same account and saved tours appear. A Google identity
   already attached to a different application account needs controlled
   resolution; the app will not merge it by email. A blocked app account must
   remain blocked. Do not log or capture test passwords.

Tenant changes have not been applied from this repository. Auth0 Management API
access or a tenant administrator is required. The prompt partial is a prepared
artifact, not evidence of a live Auth0 signup screen.

References: [confirm-password partial](https://support.auth0.com/center/s/article/Confirm-re-type-password-field-on-sign-up), [Flexible Password Policy](https://auth0.com/changelog?version=v202545), [email verification](https://auth0.com/docs/manage-users/user-accounts/verify-emails), [prompt partials](https://auth0.com/docs/customize/login-pages/universal-login/customize-signup-and-login-prompts).
