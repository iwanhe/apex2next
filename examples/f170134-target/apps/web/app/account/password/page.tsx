import { redirect } from 'next/navigation';
import { apiGetRaw, ApiError, type Session } from '../../../lib/api';
import { APP_TITLE } from '../../../lib/spec';
import { PasswordForm } from './PasswordForm';

export const metadata = { title: `Ganti Password - ${APP_TITLE}` };

/**
 * Change password for local accounts (WP9-009; APEX workspace accounts change it on the APEX login flow).
 * Outside the application shell: an account with a temporary password may reach nothing else.
 */
export default async function ChangePasswordPage() {
  let forced = false;
  try {
    const s = await apiGetRaw<Session>('/session');
    if (s.authMode !== 'local') redirect('/');
    forced = s.mustChangePassword === true;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect('/login');
    if (!(e instanceof ApiError) || e.body.code !== 'PASSWORD_CHANGE_REQUIRED') throw e;
    forced = true;
  }
  return (
    <div className="login" data-page="change-password">
      <div className="panel">
        <h1>{APP_TITLE}</h1>
        <h2>Ganti Password</h2>
        <PasswordForm forced={forced} minLength={Number(process.env.PASSWORD_MIN_LENGTH ?? 10)} />
        {!forced && <p><a href="/">Kembali</a></p>}
      </div>
    </div>
  );
}
