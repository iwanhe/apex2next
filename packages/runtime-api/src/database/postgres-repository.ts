import { PostgresDatabase } from './postgres-database';

const TABLE_IDENTIFIER = /^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?$/;
const COLUMN_IDENTIFIER = /^[a-z_][a-z0-9_]*$/;

function quoteIdentifier(identifier: string, pattern: RegExp): string {
  if (!pattern.test(identifier)) {
    throw new Error('Unsafe PostgreSQL identifier; use reviewed lowercase identifiers.');
  }
  return identifier.split('.').map((part) => '"' + part + '"').join('.');
}

/** Generic repository: identifiers are allowlisted and values are always bound. */
export class PostgresRepository<Row extends Record<string, unknown>> {
  private readonly tableSql: string;
  private readonly idColumnSql: string;
  private readonly columnSql: Map<string, string>;

  constructor(
    private readonly database: PostgresDatabase,
    table: string,
    idColumn: string,
    writableColumns: string[],
  ) {
    this.tableSql = quoteIdentifier(table, TABLE_IDENTIFIER);
    this.idColumnSql = quoteIdentifier(idColumn, COLUMN_IDENTIFIER);
    if (writableColumns.length === 0 || new Set(writableColumns).size !== writableColumns.length) {
      throw new Error('writableColumns must be non-empty and unique.');
    }
    this.columnSql = new Map(
      writableColumns.map((column) => [column, quoteIdentifier(column, COLUMN_IDENTIFIER)]),
    );
  }

  async findById(id: string | number): Promise<Row | null> {
    const result = await this.database.query<Row>(
      'SELECT * FROM ' + this.tableSql + ' WHERE ' + this.idColumnSql + ' = $1 LIMIT 1',
      [id],
    );
    return result.rows[0] ?? null;
  }

  async insert(values: Partial<Row>): Promise<Row> {
    const entries = this.orderedEntries(values);
    if (entries.length === 0) throw new Error('insert requires at least one writable field.');
    const columns = entries.map(([key]) => this.columnSql.get(key) as string);
    const placeholders = entries.map((_, index) => '$' + (index + 1));
    const sql = 'INSERT INTO ' + this.tableSql + ' (' + columns.join(', ') + ') VALUES (' +
      placeholders.join(', ') + ') RETURNING *';
    const result = await this.database.query<Row>(sql, entries.map(([, value]) => value));
    return result.rows[0];
  }

  async updateById(id: string | number, values: Partial<Row>): Promise<Row | null> {
    const entries = this.orderedEntries(values);
    if (entries.length === 0) throw new Error('updateById requires at least one writable field.');
    const assignments = entries.map(
      ([key], index) => this.columnSql.get(key) + ' = $' + (index + 1),
    );
    const sql = 'UPDATE ' + this.tableSql + ' SET ' + assignments.join(', ') +
      ' WHERE ' + this.idColumnSql + ' = $' + (entries.length + 1) + ' RETURNING *';
    const result = await this.database.query<Row>(
      sql, [...entries.map(([, value]) => value), id],
    );
    return result.rows[0] ?? null;
  }

  async deleteById(id: string | number): Promise<boolean> {
    const result = await this.database.query(
      'DELETE FROM ' + this.tableSql + ' WHERE ' + this.idColumnSql + ' = $1',
      [id],
    );
    return (result.rowCount ?? 0) > 0;
  }

  private orderedEntries(values: Partial<Row>): Array<[string, unknown]> {
    const input = values as Record<string, unknown>;
    const unknown = Object.keys(input).filter((key) => !this.columnSql.has(key));
    if (unknown.length > 0) throw new Error('Unknown or non-writable columns: ' + unknown.join(', '));
    return [...this.columnSql.keys()]
      .filter((key) => Object.prototype.hasOwnProperty.call(input, key))
      .map((key) => [key, input[key]]);
  }
}
