import type { RuntimeLovDefinition, RuntimeLovOption } from './contracts.js';

export interface RuntimeLovProvider {
  resolve(context: Readonly<Record<string, string | null>>, search: string): Promise<readonly RuntimeLovOption[]>;
}

/** Resolves LOV values through static metadata or a registered provider; never accepts SQL from the caller. */
export async function resolveRuntimeLov(
  definition: RuntimeLovDefinition,
  context: Readonly<Record<string, string | null>>,
  search = '',
  providers: ReadonlyMap<string, RuntimeLovProvider> = new Map(),
): Promise<readonly RuntimeLovOption[]> {
  if (!Number.isSafeInteger(definition.maxRows) || definition.maxRows < 1) {
    throw new Error('LOV maxRows must be a positive safe integer.');
  }
  const normalizedSearch = search.trim().toLocaleLowerCase();
  if (normalizedSearch && !definition.searchable) throw new Error('This LOV does not support search.');

  let options: readonly RuntimeLovOption[];
  if (definition.source === 'STATIC') {
    options = definition.options ?? [];
  } else {
    const providerId = definition.providerId;
    const provider = providerId ? providers.get(providerId) : undefined;
    if (!provider) throw new Error(`LOV provider is not registered: ${providerId ?? definition.id}`);
    options = await provider.resolve(context, search.trim());
  }

  const unique = new Map<string, RuntimeLovOption>();
  for (const option of options) {
    if (typeof option.value !== 'string' || typeof option.display !== 'string') continue;
    if (!unique.has(option.value)) unique.set(option.value, option);
  }
  const filtered = [...unique.values()].filter((option) => !normalizedSearch
    || option.display.toLocaleLowerCase().includes(normalizedSearch)
    || option.value.toLocaleLowerCase().includes(normalizedSearch));
  return filtered.slice(0, definition.maxRows);
}
