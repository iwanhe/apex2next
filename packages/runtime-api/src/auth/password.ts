import { randomBytes, randomInt, scrypt as scryptCb, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';

/**
 * Password hashing for local accounts (WP9-009): scrypt from node:crypto, no extra dependency.
 * Stored format: scrypt$N$r$p$<salt base64url>$<key base64url>. Parameters follow the OWASP minimum for scrypt
 * (N=2^17, r=8, p=1); verification reads them from the stored value, so they can be raised later.
 */
const scrypt = promisify(scryptCb) as (pw: string, salt: Buffer, len: number, opts: object) => Promise<Buffer>;
const N = 2 ** 17;
const R = 8;
const P = 1;
const KEY_LEN = 32;
const maxmem = (n: number, r: number) => 128 * n * r * 2;

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = await scrypt(password, salt, KEY_LEN, { N, r: R, p: P, maxmem: maxmem(N, R) });
  return `scrypt$${N}$${R}$${P}$${salt.toString('base64url')}$${key.toString('base64url')}`;
}

/** Constant-time check. A malformed stored value never matches. */
export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split('$');
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false;
  const [n, r, p] = parts.slice(1, 4).map(Number);
  if (![n, r, p].every((x) => Number.isInteger(x) && x > 0) || n > 2 ** 20 || r > 32 || p > 16) return false;
  const salt = Buffer.from(parts[4], 'base64url');
  const expected = Buffer.from(parts[5], 'base64url');
  if (salt.length < 16 || expected.length !== KEY_LEN) return false;
  const key = await scrypt(password, salt, KEY_LEN, { N: n, r, p, maxmem: maxmem(n, r) });
  return timingSafeEqual(key, expected);
}

/** A valid hash of a random password: unknown usernames are checked against it so they take the same time. */
let dummy: Promise<string> | null = null;
export function dummyHash(): Promise<string> {
  dummy ??= hashPassword(randomBytes(24).toString('base64url'));
  return dummy;
}

export interface PasswordPolicy { readonly minLength: number }

/** Returns the reasons a new password is refused (empty = accepted). Messages in the application's language. */
export function checkPolicy(policy: PasswordPolicy, username: string, password: string, current?: string): string[] {
  const out: string[] = [];
  if (password.length < policy.minLength) out.push(`Password minimal ${policy.minLength} karakter.`);
  if (password.length > 128) out.push('Password maksimal 128 karakter.');
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) out.push('Password harus berisi huruf dan angka.');
  if (username && password.toUpperCase().includes(username.toUpperCase())) out.push('Password tidak boleh memuat username.');
  if (current !== undefined && password === current) out.push('Password baru harus berbeda dari password lama.');
  return out;
}

/** Temporary password for a new or reset account: 16 characters without look-alikes, always letters and digits. */
export function temporaryPassword(): string {
  const letters = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ';
  const digits = '23456789';
  const all = letters + digits;
  const chars = Array.from({ length: 14 }, () => all[randomInt(all.length)]);
  chars.push(letters[randomInt(letters.length)], digits[randomInt(digits.length)]);
  for (let i = chars.length - 1; i > 0; i--) {
    const j = randomInt(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join('');
}
