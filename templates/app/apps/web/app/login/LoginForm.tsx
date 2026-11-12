'use client';
import { useActionState } from 'react';
import { login, type LoginState } from './actions';

export function LoginForm(props: {
  initialUsername: string; showRemember: boolean;
  labels: { username: string; password: string; remember: string; signIn: string };
  /** Item names of the APEX login page (element ids, as in APEX). */
  ids: { username: string; password: string };
}) {
  const [state, action, pending] = useActionState<LoginState, FormData>(login, { error: null, username: props.initialUsername });
  return (
    <form action={action}>
      {state.error && <div className="alert alert-error" role="alert">{state.error}</div>}
      <label htmlFor={props.ids.username}>{props.labels.username}</label>
      <input id={props.ids.username} name="username" autoComplete="username" defaultValue={state.username} required autoFocus />
      <label htmlFor={props.ids.password}>{props.labels.password}</label>
      <input id={props.ids.password} name="password" type="password" autoComplete="current-password" required />
      {props.showRemember && (
        <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" name="remember" value="Y" defaultChecked={!!props.initialUsername} /> {props.labels.remember}
        </label>
      )}
      <button className="btn btn-hot" type="submit" disabled={pending}>{props.labels.signIn}</button>
    </form>
  );
}
