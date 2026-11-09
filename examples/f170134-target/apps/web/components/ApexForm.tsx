'use client';
import Link from 'next/link';
import { useActionState } from 'react';
import type { FormBinding, FormState } from '../lib/form-actions';
import { submitApexForm } from '../lib/form-actions';

export interface FieldView {
  item: string;
  column: string;
  label: string;
  kind: 'text' | 'textarea' | 'number' | 'date' | 'select' | 'display';
  required: boolean;
  readOnly: boolean;
  options?: { display: string; value: string }[];
  nullText?: string | null;
  help?: string | null;
  /** Display text for read-only/display items (LOV display value or formatted number/date). */
  displayValue?: string;
}

export interface ButtonView {
  name: string;
  label: string;
  hot?: boolean;
  danger?: boolean;
  confirm?: string | null;
  position: 'left' | 'right';
}

/**
 * Generic APEX form dialog body: items in sequence, inline errors, buttons by position (CLOSE/DELETE left,
 * NEXT right). Read-only items render as text and are not submitted.
 */
export function ApexForm({ binding, fields, values, checksum, buttons, cancelHref, cancelLabel }: {
  binding: FormBinding; fields: FieldView[]; values: Record<string, string | null>; checksum: string | null;
  buttons: ButtonView[]; cancelHref: string; cancelLabel: string;
}) {
  const action = submitApexForm.bind(null, binding);
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, { error: null, fieldErrors: [], values: null, version: 0 });
  const current = (c: string) => state.values?.[c] ?? values[c] ?? '';
  const errorsFor = (item: string) => state.fieldErrors.filter((e) => e.field === item);
  const left = buttons.filter((b) => b.position === 'left');
  const right = buttons.filter((b) => b.position === 'right');
  const renderButton = (b: ButtonView) => (
    <button key={b.name} type="submit" name="request" value={b.name} disabled={pending}
      className={`btn${b.hot ? ' btn-hot' : ''}${b.danger ? ' btn-danger' : ''}`}
      formNoValidate
      onClick={(e) => { if (b.confirm && !window.confirm(b.confirm)) e.preventDefault(); }}>
      {b.label}
    </button>
  );
  return (
    <form action={formAction} key={state.version} data-version={state.version} noValidate>
      <div className="dialog-body">
        {(state.error || state.fieldErrors.length > 0) && (() => {
          // APEX error notification: "n error(s) have occurred", then every message (inline ones repeated below).
          const messages = [...(state.error ? [state.error] : []), ...state.fieldErrors.map((e) => e.message)];
          return (
            <div className="alert alert-error" role="alert">
              <div className="alert-title">{messages.length === 1 ? '1 error has occurred' : `${messages.length} errors have occurred`}</div>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>{messages.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </div>
          );
        })()}
        {checksum && <input type="hidden" name="checksum" value={checksum} />}
        {fields.map((f) => {
          const errs = errorsFor(f.item);
          const id = f.item;
          const common = { id, name: f.column, 'aria-invalid': errs.length > 0 || undefined, 'aria-describedby': errs.length ? `${id}_error` : undefined };
          let control: React.ReactNode;
          if (f.readOnly || f.kind === 'display') {
            control = <div className="value" id={id} data-testid={id}>{f.displayValue ?? current(f.column)}</div>;
          } else if (f.kind === 'textarea') {
            control = <textarea {...common} defaultValue={current(f.column)} />;
          } else if (f.kind === 'select') {
            control = (
              <select {...common} defaultValue={current(f.column)}>
                {f.nullText !== undefined && <option value="">{f.nullText ?? ''}</option>}
                {(f.options ?? []).map((o) => <option key={o.value} value={o.value}>{o.display}</option>)}
                {current(f.column) && !(f.options ?? []).some((o) => o.value === current(f.column)) &&
                  <option value={current(f.column)}>{current(f.column)}</option>}
              </select>
            );
          } else {
            control = <input {...common} type={f.kind === 'date' ? 'date' : 'text'} inputMode={f.kind === 'number' ? 'decimal' : undefined} defaultValue={current(f.column)} />;
          }
          return (
            <div className="field" key={f.item}>
              <label htmlFor={id} className={f.required && !f.readOnly ? 'required' : undefined}>{f.label}</label>
              <div>
                {control}
                {f.help && <div className="help">{f.help}</div>}
                {errs.map((e, i) => <div key={i} className="error" id={`${id}_error`}>{e.message}</div>)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="dialog-footer">
        <div className="right"><Link className="btn" href={cancelHref}>{cancelLabel}</Link>{left.map(renderButton)}</div>
        <div className="right">{right.map(renderButton)}</div>
      </div>
    </form>
  );
}
