'use client';
import { useActionState } from 'react';
import { changePassword, type PasswordState } from './actions';

const FIELDS = [
  { name: 'current', field: 'current_password', label: 'Password Lama', auto: 'current-password' },
  { name: 'next', field: 'new_password', label: 'Password Baru', auto: 'new-password' },
  { name: 'confirm', field: 'confirm_password', label: 'Ulangi Password Baru', auto: 'new-password' },
] as const;

export function PasswordForm({ forced, minLength }: { forced: boolean; minLength: number }) {
  const [state, action, pending] = useActionState<PasswordState, FormData>(changePassword, { errors: [] });
  const page = state.errors.filter((e) => !e.field);
  return (
    <form action={action}>
      {forced && <div className="alert" role="status">Password sementara harus diganti sebelum melanjutkan.</div>}
      {page.length > 0 && <div className="alert alert-error" role="alert">{page.map((e) => <p key={e.message}>{e.message}</p>)}</div>}
      {FIELDS.map((f) => {
        const errs = state.errors.filter((e) => e.field === f.field);
        return (
          <div className="field" key={f.name}>
            <label htmlFor={`pw_${f.name}`}>{f.label}</label>
            <input id={`pw_${f.name}`} name={f.name} type="password" autoComplete={f.auto} required
              aria-invalid={errs.length > 0} aria-describedby={errs.length ? `pw_${f.name}_err` : undefined} />
            {errs.length > 0 && <span className="error" id={`pw_${f.name}_err`}>{errs.map((e) => e.message).join(' ')}</span>}
          </div>
        );
      })}
      <p className="hint">Minimal {minLength} karakter, berisi huruf dan angka, tidak memuat username.</p>
      <button className="btn btn-hot" type="submit" disabled={pending}>Ganti Password</button>
    </form>
  );
}
