import { Injectable } from '@nestjs/common';
import { BusinessTx } from './context';
import { errors } from './errors';

/**
 * Replaces APX_DEMO_DOC_PKG.NEXT_NO (install.sql lines 348-378).
 *
 * BR-DOC-01 number = PREFIX-YYYY-NNNN, prefix from apx_demo_doc_types, period = year of p_date
 *           (default: transaction clock, like SYSDATE).
 * BR-DOC-02 the counter row is created on first use of a period and incremented in the caller's
 *           transaction: a rollback releases the number (gapless) and concurrent callers serialize on the
 *           counter row. INSERT ... ON CONFLICT replaces MERGE + UPDATE and removes the source race where two
 *           first-of-period callers could fail on the primary key (WP9.2 race finding).
 * BR-DOC-03 Oracle LPAD(n, 4, '0') truncates n > 9999 (10000 -> '1000'), which duplicates numbers and then
 *           fails on the unique key. The target raises an explicit error instead (DEV-04).
 */
@Injectable()
export class NumberingService {
  async nextNo(tx: BusinessTx, docType: string, date?: { year: string }): Promise<string> {
    const prefix = await tx.query<{ prefix: string }>(
      'SELECT prefix FROM app.apx_demo_doc_types WHERE doc_type = $1', [docType]);
    if (prefix.rowCount === 0) throw errors.notFound(`Jenis dokumen ${docType}`, 'BR-DOC-01');
    const period = (date ?? tx.now).year;
    const counter = await tx.query<{ last_no: string }>(
      `INSERT INTO app.apx_demo_doc_seq AS s (doc_type, period, last_no)
       VALUES ($1, $2, 1)
       ON CONFLICT (doc_type, period) DO UPDATE SET last_no = s.last_no + 1
       RETURNING last_no`,
      [docType, period]);
    const n = BigInt(counter.rows[0].last_no);
    if (n > 9999n) throw errors.numberingCapacity(docType, period);
    return `${prefix.rows[0].prefix}-${period}-${n.toString().padStart(4, '0')}`;
  }
}
