import { Injectable } from '@nestjs/common';
import { BusinessTx } from './context';
import { errors } from './errors';

/**
 * Master-data write paths. Replace the normalization/audit triggers APX_DEMO_USER_ROLES_TRG,
 * APX_DEMO_DEPARTMENTS_TRG and APX_DEMO_ITEMS_TRG (install.sql lines 735-777):
 * BR-MD-01 codes are stored upper-case; BR-AUD-01 created_* on insert, updated_* on insert and update.
 */
interface EntitySpec {
  table: string;
  id: string;
  columns: string[];
  upper: string[];
}

const SPECS = {
  userRoles: { table: 'app.apx_demo_user_roles', id: 'user_role_id', columns: ['username', 'role_code'], upper: ['username', 'role_code'] },
  departments: { table: 'app.apx_demo_departments', id: 'department_id', columns: ['dept_code', 'dept_name', 'active_yn'], upper: ['dept_code'] },
  items: {
    table: 'app.apx_demo_items', id: 'item_id',
    columns: ['item_code', 'item_name', 'category', 'uom', 'std_price', 'active_yn'], upper: ['item_code', 'uom'],
  },
} satisfies Record<string, EntitySpec>;

export type MasterDataEntity = keyof typeof SPECS;

function normalize(spec: EntitySpec, values: Record<string, unknown>): Record<string, unknown> {
  const unknown = Object.keys(values).filter((k) => !spec.columns.includes(k));
  if (unknown.length) throw errors.invalidInput(`Kolom tidak dikenal: ${unknown.join(', ')}`);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(values)) {
    const value = v === '' ? null : v; // Oracle '' is NULL
    out[k] = spec.upper.includes(k) && typeof value === 'string' ? value.toUpperCase() : value;
  }
  return out;
}

@Injectable()
export class MasterDataService {
  async create(tx: BusinessTx, entity: MasterDataEntity, values: Record<string, unknown>) {
    const spec: EntitySpec = SPECS[entity];
    const v = normalize(spec, values);
    const cols = Object.keys(v);
    const n = cols.length;
    const r = await tx.query(
      `INSERT INTO ${spec.table} (${[...cols, 'created_by', 'created_on', 'updated_by', 'updated_on'].join(', ')})
       VALUES (${[...cols.map((_, i) => `$${i + 1}`), `$${n + 1}`, `$${n + 2}`, `$${n + 1}`, `$${n + 2}`].join(', ')})
       RETURNING *`,
      [...cols.map((c) => v[c]), tx.principal.username, tx.now.timestamp]);
    return r.rows[0];
  }

  async update(tx: BusinessTx, entity: MasterDataEntity, id: number, values: Record<string, unknown>) {
    const spec: EntitySpec = SPECS[entity];
    const v = normalize(spec, values);
    const cols = Object.keys(v);
    const sets = [...cols.map((c, i) => `${c} = $${i + 2}`), `updated_by = $${cols.length + 2}`, `updated_on = $${cols.length + 3}`];
    const r = await tx.query(
      `UPDATE ${spec.table} SET ${sets.join(', ')} WHERE ${spec.id} = $1 RETURNING *`,
      [id, ...cols.map((c) => v[c]), tx.principal.username, tx.now.timestamp]);
    if (r.rowCount === 0) throw errors.notFound(`${entity} ${id}`, 'BR-MD-01');
    return r.rows[0];
  }
}
