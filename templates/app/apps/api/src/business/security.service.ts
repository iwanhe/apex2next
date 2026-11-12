import { Injectable } from '@nestjs/common';
import { BusinessTx, errors, evaluateScheme, schemeMessage, type SchemeDef } from '@apex2next/runtime-api';
import { RULES } from './security';
import { SCHEMES } from './security-schemes.generated';

/** APEX authorization schemes: the generated proposal, overridden by the reviewed rules of security.ts. */
@Injectable()
export class SecurityService {
  definition(name: string): SchemeDef | undefined {
    const def = SCHEMES[name];
    return def && { ...def, rule: RULES[name] ?? def.rule };
  }

  names(): string[] {
    return Object.keys(SCHEMES);
  }

  isAuthorized(tx: BusinessTx, name: string): Promise<boolean> {
    return evaluateScheme(tx, this.definition(name));
  }

  message(tx: BusinessTx, name: string): string {
    return schemeMessage(this.definition(name), name).replace(/&APP_USER\./g, tx.principal.username);
  }

  async authorize(tx: BusinessTx, name: string | null | undefined): Promise<void> {
    if (!name) return;
    if (!(await this.isAuthorized(tx, name))) throw errors.forbidden(this.message(tx, name));
  }
}
