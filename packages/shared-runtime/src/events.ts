import type { RuntimeEventAction } from './contracts.js';

const ALLOWED_ACTIONS: Readonly<Record<RuntimeEventAction['event'], readonly RuntimeEventAction['action'][]>> = {
  CHANGE: ['SHOW', 'HIDE', 'SET_VALUE', 'REFRESH', 'ENABLE', 'DISABLE', 'SUBMIT'],
  CLICK: ['SHOW', 'HIDE', 'SET_VALUE', 'REFRESH', 'ENABLE', 'DISABLE', 'SUBMIT'],
  DIALOG_CLOSED: ['SHOW', 'HIDE', 'REFRESH', 'ENABLE', 'DISABLE'],
  PAGE_LOAD: ['SHOW', 'HIDE', 'SET_VALUE', 'REFRESH', 'ENABLE', 'DISABLE'],
  SUBMIT: ['SHOW', 'HIDE', 'REFRESH'],
};

/** Validates and orders declarative dynamic actions; no source JavaScript or PL/SQL is evaluated. */
export function planRuntimeEventActions(
  event: RuntimeEventAction['event'],
  actions: readonly RuntimeEventAction[],
  knownTargetIds: ReadonlySet<string>,
): readonly RuntimeEventAction[] {
  const selected = actions.filter((action) => action.event === event);
  const ids = new Set<string>();
  const sequences = new Set<number>();
  for (const action of selected) {
    if (!action.id || ids.has(action.id)) throw new Error('Runtime event action IDs must be non-empty and unique.');
    ids.add(action.id);
    if (!Number.isSafeInteger(action.sequence) || action.sequence < 1 || sequences.has(action.sequence)) {
      throw new Error('Runtime event action sequence must be a unique positive safe integer.');
    }
    sequences.add(action.sequence);
    if (!ALLOWED_ACTIONS[event].includes(action.action)) {
      throw new Error(`Action ${action.action} is not supported for event ${event}.`);
    }
    if (action.targetIds.length === 0 || action.targetIds.some((target) => !knownTargetIds.has(target))) {
      throw new Error(`Runtime event action ${action.id} references an unknown or empty target.`);
    }
  }
  return [...selected].sort((left, right) => left.sequence - right.sequence);
}
