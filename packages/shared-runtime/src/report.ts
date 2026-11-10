import type { RuntimeReportDefinition, RuntimeReportPlan, RuntimeReportQuery } from './contracts.js';

/** Produces a validated, database-agnostic report plan; SQL generation remains adapter-owned. */
export function createRuntimeReportPlan(
  definition: RuntimeReportDefinition,
  query: RuntimeReportQuery,
): RuntimeReportPlan {
  const columns = new Map(definition.columns.map((column) => [column.name.toLowerCase(), column]));
  const requestedSort = (query.sort ?? definition.defaultSort.column).toLowerCase();
  const sortColumn = columns.get(requestedSort);
  if (!sortColumn || !sortColumn.sortable || sortColumn.hidden) {
    throw new Error(`Unsupported report sort column: ${query.sort ?? requestedSort}`);
  }
  const requestedDirection = (query.direction ?? definition.defaultSort.direction).toUpperCase();
  if (requestedDirection !== 'ASC' && requestedDirection !== 'DESC') {
    throw new Error('Report direction must be ASC or DESC.');
  }

  const requestedPage = query.page ?? 1;
  if (!Number.isFinite(requestedPage) || requestedPage < 1) {
    throw new Error('Report page must be a finite positive number.');
  }
  const page = Math.floor(requestedPage);
  if (!Number.isSafeInteger(page)) throw new Error('Report page must be a safe positive integer.');

  const requestedPageSize = query.pageSize ?? definition.defaultPageSize;
  if (!Number.isFinite(requestedPageSize) || requestedPageSize < 1) {
    throw new Error('Report page size must be a finite positive number.');
  }
  if (!Number.isSafeInteger(definition.maxPageSize) || definition.maxPageSize < 1) {
    throw new Error('Report definition maxPageSize must be a positive safe integer.');
  }
  const pageSize = Math.min(definition.maxPageSize, Math.max(1, Math.floor(requestedPageSize)));
  const offset = (page - 1) * pageSize;
  if (!Number.isSafeInteger(offset)) throw new Error('Report offset exceeds the safe integer range.');

  const search = (query.search ?? '').trim();
  if (search && !definition.searchable) throw new Error('This report does not support search.');
  return { search, sort: sortColumn.name, direction: requestedDirection, page, pageSize, offset };
}
