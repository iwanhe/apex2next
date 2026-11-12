import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { LOGIN_PAGE } from '../../lib/app-routes.generated';
import { APP_TITLE, button, item, page } from '../../lib/spec';
import { USERNAME_COOKIE } from '../../lib/session';
import { LoginForm } from './LoginForm';

const L = LOGIN_PAGE;
const prompt = (name: string | null, fallback: string) => (name ? item(L.page, name).prompt ?? fallback : fallback);

export const metadata: Metadata = { title: String(page(L.page).title).replace('&APP_TITLE.', APP_TITLE ?? '') };

/**
 * The APEX login page of the application (LOGIN_PAGE, generated). The remember-username item is displayed only
 * when persistent cookies are enabled on the APEX instance; the target reads that switch from LOGIN_REMEMBER_USERNAME.
 */
export default async function LoginPage() {
  const remembered = (await cookies()).get(USERNAME_COOKIE)?.value ?? '';
  return (
    <div className="login" data-apex-page={L.page}>
      <div className="panel">
        <h1>{APP_TITLE}</h1>
        <LoginForm
          initialUsername={remembered}
          showRemember={process.env.LOGIN_REMEMBER_USERNAME === 'true' && L.remember !== null}
          ids={{ username: L.username, password: L.password }}
          labels={{
            username: prompt(L.username, 'Username'), password: prompt(L.password, 'Password'),
            remember: prompt(L.remember, 'Remember username'),
            signIn: L.button ? button(L.page, L.button).buttonImageAlt : 'Sign In',
          }}
        />
      </div>
    </div>
  );
}
