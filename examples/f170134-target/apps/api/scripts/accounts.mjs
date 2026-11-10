#!/usr/bin/env node
// WP9-009 local account administration (operator CLI; replaces APEX Workspace Administration > Manage Users).
// Temporary passwords are printed once to this terminal only and must be changed at the first login.
// Never paste them into chat, tickets or logs; hand them over through an agreed channel.
//
//   node scripts/accounts.mjs list
//   node scripts/accounts.mjs create <username> [--by OPERATOR]
//   node scripts/accounts.mjs import-roles [--by OPERATOR]   accounts for every user in app.apx_demo_user_roles
//   node scripts/accounts.mjs reset <username>               new temporary password, sessions revoked, unlocked
//   node scripts/accounts.mjs unlock|lock|deactivate|activate|revoke <username>
//
// Requires DATABASE_URL and a built API (dist/) for the password hashing code.
import { createRequire } from 'node:module';
import pg from 'pg';

const require = createRequire(import.meta.url);
const { hashPassword, temporaryPassword } = require('../dist/auth/password.js');

const [cmd, arg, ...rest] = process.argv.slice(2);
const by = (() => {
  const i = rest.indexOf('--by');
  const v = i >= 0 ? rest[i + 1] : process.env.ACCOUNT_OPERATOR ?? process.env.USER ?? 'OPERATOR';
  return String(v).trim().toUpperCase();
})();
const norm = (u) => {
  const v = String(u ?? '').trim().toUpperCase();
  if (!v) usage(`username required for ${cmd}`);
  return v;
};
function usage(msg) {
  if (msg) console.error(msg);
  console.error('usage: accounts.mjs list | create <user> | import-roles | reset <user> | unlock|lock|deactivate|activate|revoke <user> [--by OPERATOR]');
  process.exit(2);
}
if (!process.env.DATABASE_URL) usage('DATABASE_URL is required');

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL, max: 1 });
const q = (sql, params) => pool.query(sql, params);
const event = (u, e, detail = null) => q('INSERT INTO iam.account_events (username, event, actor, detail) VALUES ($1, $2, $3, $4)', [u, e, by, detail]);

async function create(username) {
  const temp = temporaryPassword();
  const r = await q(`INSERT INTO iam.accounts (username, password_hash, must_change_password, created_by, updated_by)
                     VALUES ($1, $2, true, $3, $3) ON CONFLICT (username) DO NOTHING RETURNING username`,
  [username, await hashPassword(temp), by]);
  if (!r.rowCount) return console.log(`${username}\texists (unchanged)`);
  await event(username, 'CREATED');
  console.log(`${username}\ttemporary password: ${temp}`);
}

async function update(username, sql, ev, detail = null, params = []) {
  const r = await q(`UPDATE iam.accounts SET ${sql}, updated_by = $2, updated_at = now() WHERE username = $1 RETURNING username`, [username, by, ...params]);
  if (!r.rowCount) {
    console.error(`${username}: no such account`);
    process.exitCode = 1;
    return false;
  }
  await event(username, ev, detail);
  return true;
}

try {
  switch (cmd) {
    case 'list': {
      const r = await q(`SELECT a.username, a.active, a.must_change_password AS temp_pw,
                                coalesce(a.locked_until > now(), false) AS locked, a.failed_attempts,
                                to_char(a.last_login_at, 'YYYY-MM-DD HH24:MI') AS last_login,
                                (SELECT string_agg(role_code, ',' ORDER BY role_code) FROM app.apx_demo_user_roles ur
                                  WHERE upper(ur.username) = a.username) AS roles
                           FROM iam.accounts a ORDER BY a.username`);
      console.table(r.rows);
      break;
    }
    case 'create':
      await create(norm(arg));
      break;
    case 'import-roles': {
      const r = await q(`SELECT DISTINCT upper(btrim(username)) AS u FROM app.apx_demo_user_roles ORDER BY 1`);
      for (const { u } of r.rows) await create(u);
      break;
    }
    case 'reset': {
      const u = norm(arg);
      const temp = temporaryPassword();
      if (await update(u, `password_hash = $3, must_change_password = true, failed_attempts = 0, locked_until = NULL,
                           session_version = session_version + 1, password_changed_at = now()`, 'PASSWORD_RESET', null,
      [await hashPassword(temp)])) {
        console.log(`${u}\ttemporary password: ${temp}`);
      }
      break;
    }
    case 'unlock':
      if (await update(norm(arg), 'failed_attempts = 0, locked_until = NULL', 'UNLOCKED')) console.log('unlocked');
      break;
    case 'lock':
      if (await update(norm(arg), "locked_until = 'infinity', session_version = session_version + 1", 'LOCKED', 'by operator')) console.log('locked');
      break;
    case 'deactivate':
      if (await update(norm(arg), 'active = false, session_version = session_version + 1', 'DEACTIVATED')) console.log('deactivated');
      break;
    case 'activate':
      if (await update(norm(arg), 'active = true', 'ACTIVATED')) console.log('activated');
      break;
    case 'revoke':
      if (await update(norm(arg), 'session_version = session_version + 1', 'SESSIONS_REVOKED')) console.log('sessions revoked');
      break;
    default:
      usage(cmd ? `unknown command ${cmd}` : undefined);
  }
} finally {
  await pool.end();
}
