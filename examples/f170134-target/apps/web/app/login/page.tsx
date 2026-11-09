import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { APP_TITLE, button, item, page } from '../../lib/spec';
import { USERNAME_COOKIE } from '../../lib/session';
import { LoginForm } from './LoginForm';

export const metadata: Metadata = { title: String(page(9999).title).replace('&APP_TITLE.', APP_TITLE ?? '') };

/**
 * Page 9999 Login. P9999_REMEMBER is displayed only when persistent cookies are enabled on the APEX instance
 * (apex_authentication.persistent_cookies_enabled); the target reads that switch from LOGIN_REMEMBER_USERNAME.
 */
export default async function LoginPage() {
  const remembered = (await cookies()).get(USERNAME_COOKIE)?.value ?? '';
  return (
    <div className="login" data-apex-page="9999">
      <div className="panel">
        <h1>{APP_TITLE}</h1>
        <LoginForm
          initialUsername={remembered}
          showRemember={process.env.LOGIN_REMEMBER_USERNAME === 'true'}
          labels={{
            username: item(9999, 'P9999_USERNAME').prompt, password: item(9999, 'P9999_PASSWORD').prompt,
            remember: item(9999, 'P9999_REMEMBER').prompt, signIn: button(9999, 'LOGIN').buttonImageAlt,
          }}
        />
      </div>
    </div>
  );
}
