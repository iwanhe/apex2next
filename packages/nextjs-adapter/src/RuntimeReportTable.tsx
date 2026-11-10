import type { ReactNode } from 'react';
import type { RuntimeReportColumn } from '@apex2next/shared-runtime';

export interface RuntimeReportTableProps {
  readonly columns: readonly RuntimeReportColumn[];
  readonly rows: readonly Readonly<Record<string, string | number | null>>[];
  readonly rowKey?: string;
  readonly emptyMessage?: string;
  readonly renderCell?: (column: RuntimeReportColumn, value: string | number | null, row: Readonly<Record<string, string | number | null>>) => ReactNode;
}

/** Accessible, server-component-compatible report table. Query construction and SQL remain API-owned. */
export function RuntimeReportTable({
  columns,
  rows,
  rowKey,
  emptyMessage = 'No data found.',
  renderCell,
}: RuntimeReportTableProps) {
  const visible = columns.filter((column) => !column.hidden);
  return (
    <table>
      <thead>
        <tr>{visible.map((column) => <th key={column.name} scope="col">{column.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr><td colSpan={Math.max(visible.length, 1)}>{emptyMessage}</td></tr>
        ) : rows.map((row, index) => (
          <tr key={rowKey && row[rowKey] !== null && row[rowKey] !== undefined ? String(row[rowKey]) : index}>
            {visible.map((column) => {
              const value = row[column.name] ?? null;
              return <td key={column.name}>{renderCell ? renderCell(column, value, row) : value === null ? '' : String(value)}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
