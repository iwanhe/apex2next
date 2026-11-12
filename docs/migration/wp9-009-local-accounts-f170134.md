# WP9-009 — Local accounts for app 170134

**Status:** Implemented on branch `feat/foundation-and-architecture-docs`. The owner decided on 2026-11-10 to start with **local accounts in the application** ("akun lokal di aplikasi dahulu"). An external identity provider (Entra ID, Keycloak, SAP IAS) can replace it later; the token and guard design leaves room for that.

## 1. Why, and what changes for users

The source uses Oracle APEX workspace accounts. APEX does not export password hashes, so **no password can be migrated**. Every user therefore gets an account with a **temporary password** and must change it at the first sign-in.

Roles do not change. They stay in `APX_DEMO_USER_ROLES` and are managed on page 500, as in APEX. The account username must equal the username in that table. A user with an account but no role is refused by APP_USERS, exactly like the source.

## 2. Design

| Part | Implementation |
|---|---|
| Storage | Schema `iam`, migration `0004_wp9009_local_accounts.sql` (hand-written, reviewed). It is separate from schema `app`, the converted source schema, so it survives a reload of the APEX data. Table `iam.accounts` holds the username, password hash, temporary-password flag, active flag, failed attempts, lock time and session version. Table `iam.account_events` is the audit trail (no passwords). |
| Password hash | scrypt (Node `crypto`, no extra dependency), N=2^17, r=8, p=1, 16-byte salt, stored as `scrypt$N$r$p$salt$key`. Verification is constant-time. Unknown usernames are checked against a dummy hash, so they take the same time. |
| Password policy | At least `PASSWORD_MIN_LENGTH` (default 10) characters, letters and digits, does not contain the username, differs from the old password. |
| Login | `AUTH_MODE=local`. Unknown, inactive, locked and wrong-password attempts all return "Invalid Login Credentials" (the APEX text). |
| Lockout | After `LOGIN_MAX_FAILURES` (default 5) consecutive failures the account locks for `LOGIN_LOCK_MINUTES` (default 15). A successful login resets the count. APEX workspace accounts instead stay locked until an administrator unlocks them; the operator can do that with `lock`. |
| Throttling | `LOGIN_RATE_PER_MINUTE` (default 20) login attempts per client per minute, answered with HTTP 429. The web tier passes the browser address (`cf-connecting-ip`, else `x-forwarded-for`) in `x-forwarded-for`, and the API trusts it only with `TRUST_PROXY=1`. Set that only behind a proxy that overwrites these headers, such as Cloudflare Tunnel. Without it, every login comes from the web tier and the limit applies to all users together, so size it accordingly. The counter is in memory, which is enough for one API instance. |
| Session and revocation | The HMAC session token carries the account's `session_version`. The guard checks it, plus "active" and "not locked", on every request. A password change, Sign Out, reset, deactivation or `revoke` raises the version, which ends **all** sessions of the account. |
| Temporary password | Handed over **by e-mail** (owner decision 2026-11-10). It therefore expires after `TEMP_PASSWORD_HOURS` (default 72, set by the CLI on create/reset, migration 0005); an expired one is refused like a wrong password and logged as "temporary password expired". A token issued with a temporary password reaches only `/auth/password` and `/auth/logout`. Everything else answers `PASSWORD_CHANGE_REQUIRED`, and the web sends the user to `/account/password`. |
| Web | Login handles the forced change. The new page `/account/password` sits outside the application shell. The navigation bar shows "Ganti Password" in local mode. Sign Out revokes the session in the API. |
| Administration | Operator CLI `apps/api/scripts/accounts.mjs` (replaces Workspace Administration > Manage Users): `list`, `create`, `import-roles` (one account per user in the role table), `reset`, `unlock`, `lock`, `deactivate`, `activate`, `revoke`. A temporary password is printed once, to the operator's terminal only. |
| Dev mode | `AUTH_MODE=dev` (one shared password) stays for tests and parity runs only. It is refused with `NODE_ENV=production`. |

## 3. Verification

- **API integration tests** (`auth-local.integration.test.js`):
  - hashing and policy;
  - generic answer for unknown users;
  - forced change and field errors;
  - revocation after a password change and after Sign Out;
  - lockout after 3 failures (audit trail checked, no passwords in it);
  - unlock, deactivate (a live token stops working), activate, reset;
  - an expired temporary password is refused, the default expiry is 72 h, and a password change clears it;
  - a user without a role refused by APP_USERS;
  - rate limit (HTTP 429 on the 4th attempt with a limit of 3).
- **Browser test** (`e2e/test_wp9009_local_accounts.py`, Chromium):
  - wrong password;
  - temporary password, then the forced change page; the application is unreachable until the password is changed;
  - policy message, then a successful change;
  - Sign Out, after which a copied session cookie no longer works;
  - sign-in with the new password.
- **WP9.7 rehearsal:**
  - R5 creates a local account;
  - R6 backs up schemas `app` and `iam`;
  - R8 restores them, then signs in with the temporary password, changes it and reads the reports.

  The restore therefore includes the accounts.

## 4. Owner decisions (2026-11-10)

- **F-04 row-level ownership:** any REQUESTER/MANAGER may change requests of other users, as in the source. No ownership rule is added.
- **Temporary passwords by e-mail.** E-mail is not a secure channel: a mailbox that is forwarded, shared or compromised reveals the password. The residual risk is limited by these measures:
  - the password expires after 72 h;
  - it works only to set a new password, so nothing in the application is reachable with it;
  - once the user has changed it, the e-mailed password is worthless; if someone else used it first, the user's own sign-in fails, and the user reports it;
  - lockout and the audit trail stay in place.

  Recommended practice for operators:
  - send to the user's own company mailbox only;
  - put the password in the e-mail without the username, or send the username separately;
  - delete the sent mail;
  - never put it in the ticket.

## 5. Open points (gate WP9-009 stays WARN)


- **No account administration screen.** The CLI is for operators. A page like APEX "Manage Users" can follow if needed.
- **No MFA and no single sign-on.** These come with an external identity provider later.
- **Security review and sign-off** of this design.

## 6. Go-live steps for accounts

1. Apply migrations 0004 and 0005 (they run with the others).
2. Run `node apps/api/scripts/accounts.mjs import-roles --by <operator>` after the data load. It creates one account for each user in the role table and prints the temporary passwords.
3. E-mail each temporary password to the user's company mailbox within 72 hours of creating it (otherwise run `reset`). Users change it at the first sign-in.
4. Start the API with `AUTH_MODE=local`, a fresh `SESSION_SECRET` (at least 32 characters, kept in the secret store) and `TRUST_PROXY=1` only behind a proxy that overwrites the client-address headers (e.g. Cloudflare Tunnel).
