'use client';
import { useActionState } from 'react';
import { login, type LoginState } from './actions';

export function LoginForm(props: {
  initialUsername: string; showRemember: boolean;
  labels: { username: string; password: string; remember: string; signIn: string };
}) {
  const [state, action, pending] = useActionState<LoginState, FormData>(login, { error: null, username: props.initialUsername });
  return (
    <form action={action}>
      {state.error && <div className="alert alert-error" role="alert">{state.error}</div>}
      <label htmlFor="P9999_USERNAME">{props.labels.username}</label>
      <input id="P9999_USERNAME" name="username" autoComplete="username" defaultValue={state.username} required autoFocus />
      <label htmlFor="P9999_PASSWORD">{props.labels.password}</label>
      <input id="P9999_PASSWORD" name="password" type="password" autoComplete="current-password" required />
      {props.showRemember && (
        <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" name="remember" value="Y" defaultChecked={!!props.initialUsername} /> {props.labels.remember}
        </label>
      )}
      <button className="btn btn-hot" type="submit" disabled={pending}>{props.labels.signIn}</button>
    </form>
  );
}
