import type { RuntimeFieldError, RuntimeItem, RuntimeValidationResult } from './contracts.js';

const NUMBER_PATTERN = /^[-+]?(?:\d+(?:\.\d*)?|\.\d+)$/;
const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function normalize(value: unknown, item: RuntimeItem): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  let result = String(value);
  if (item.trimSpaces === 'BOTH') result = result.trim();
  if (item.trimSpaces === 'LEADING') result = result.trimStart();
  if (item.trimSpaces === 'TRAILING') result = result.trimEnd();
  return result === '' ? null : result;
}

function validIsoDate(value: string): boolean {
  const match = ISO_DATE_PATTERN.exec(value);
  if (!match) return false;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return date.getUTCFullYear() === Number(match[1])
    && date.getUTCMonth() === Number(match[2]) - 1
    && date.getUTCDate() === Number(match[3]);
}

/**
 * Validates submitted page items without executing source expressions.
 * Only writable items are accepted; read-only/display items are ignored and cannot be overridden.
 */
export function validateRuntimeItems(
  items: readonly RuntimeItem[],
  input: Readonly<Record<string, unknown>>,
): RuntimeValidationResult {
  const writable = items.filter((item) => item.writable);
  const byName = new Map(writable.map((item) => [item.name, item]));
  const unknown = Object.keys(input).filter((name) => !byName.has(name));
  if (unknown.length) {
    return {
      values: {},
      errors: unknown.map((field): RuntimeFieldError => ({
        field,
        message: 'Unknown or non-writable page item.',
      })),
    };
  }

  const values: Record<string, string | null> = {};
  const errors: RuntimeFieldError[] = [];
  for (const item of writable) {
    const value = normalize(input[item.name], item);
    values[item.name] = value;
    if (value === null) {
      if (item.required) errors.push({ field: item.name, message: `${item.label} must have some value.` });
      continue;
    }

    if (item.dataType === 'NUMBER') {
      const number = Number(value);
      if (!NUMBER_PATTERN.test(value) || !Number.isFinite(number)) {
        errors.push({ field: item.name, message: `${item.label} must be Numeric.` });
      } else if ((item.minValue !== undefined && number < item.minValue)
        || (item.maxValue !== undefined && number > item.maxValue)) {
        errors.push({ field: item.name, message: `${item.label} is outside the permitted range.` });
      }
    } else if (item.dataType === 'DATE' && !validIsoDate(value)) {
      errors.push({ field: item.name, message: `${item.label} must use a valid YYYY-MM-DD date.` });
    } else if (item.maxLength !== undefined && value.length > item.maxLength) {
      errors.push({ field: item.name, message: `${item.label} exceeds the maximum length of ${item.maxLength}.` });
    }
  }
  return { values, errors };
}
