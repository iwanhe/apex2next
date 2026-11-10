import type { FormHTMLAttributes, ReactNode } from 'react';
import type { RuntimeFieldError, RuntimeItem } from '@apex2next/shared-runtime';

export interface RuntimeLovOption {
  readonly display: string;
  readonly value: string;
}

export interface RuntimeFormField extends RuntimeItem {
  readonly options?: readonly RuntimeLovOption[];
  readonly helpText?: string;
}

export interface RuntimeFormProps extends Omit<FormHTMLAttributes<HTMLFormElement>, 'children'> {
  readonly fields: readonly RuntimeFormField[];
  readonly values?: Readonly<Record<string, string | null>>;
  readonly errors?: readonly RuntimeFieldError[];
  readonly children?: ReactNode;
}

/** Server-component-compatible form renderer. It contains no client state or source-expression execution. */
export function RuntimeForm({
  fields,
  values = {},
  errors = [],
  children,
  ...formProps
}: RuntimeFormProps) {
  const errorMap = new Map<string, string[]>();
  for (const error of errors) {
    errorMap.set(error.field, [...(errorMap.get(error.field) ?? []), error.message]);
  }

  return (
    <form {...formProps}>
      {fields.map((field) => {
        const value = values[field.name] ?? '';
        const fieldErrors = errorMap.get(field.name) ?? [];
        const id = field.id;
        const describedBy = fieldErrors.length ? `${id}-errors` : undefined;
        let control: ReactNode;

        if (!field.writable || field.kind === 'DISPLAY') {
          control = <output id={id} data-testid={id}>{value}</output>;
        } else if (field.kind === 'TEXTAREA') {
          control = <textarea id={id} name={field.name} defaultValue={value} required={field.required}
            aria-invalid={fieldErrors.length > 0 || undefined} aria-describedby={describedBy} />;
        } else if (field.kind === 'SELECT' || field.kind === 'RADIO' || field.kind === 'CHECKBOX') {
          control = (
            <select id={id} name={field.name} defaultValue={value} required={field.required}
              aria-invalid={fieldErrors.length > 0 || undefined} aria-describedby={describedBy}>
              <option value="">—</option>
              {(field.options ?? []).map((option) => (
                <option key={option.value} value={option.value}>{option.display}</option>
              ))}
            </select>
          );
        } else {
          const type = field.kind === 'NUMBER' ? 'number'
            : field.kind === 'DATE' ? 'date'
            : field.kind === 'PASSWORD' ? 'password'
            : field.kind === 'HIDDEN' ? 'hidden' : 'text';
          control = <input id={id} name={field.name} type={type} defaultValue={value}
            required={field.required} readOnly={!field.writable}
            min={field.minValue} max={field.maxValue} maxLength={field.maxLength}
            aria-invalid={fieldErrors.length > 0 || undefined} aria-describedby={describedBy} />;
        }

        if (field.kind === 'HIDDEN') return <div key={field.id}>{control}</div>;
        return (
          <div key={field.id} className="apex2next-field">
            <label htmlFor={id}>{field.label}{field.required && field.writable ? ' *' : ''}</label>
            {control}
            {field.helpText ? <small>{field.helpText}</small> : null}
            {fieldErrors.length ? (
              <ul id={describedBy} role="alert">
                {fieldErrors.map((message, index) => <li key={index}>{message}</li>)}
              </ul>
            ) : null}
          </div>
        );
      })}
      {children}
    </form>
  );
}
