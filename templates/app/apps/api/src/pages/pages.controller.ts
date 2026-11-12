import { Body, Controller, Delete, Get, Inject, Param, Post, Put, Query } from '@nestjs/common';
import { Actor, AUTH_CONFIG, errors } from '@apex2next/runtime-api';
import type { AuthConfig, Principal } from '@apex2next/runtime-api';
import { PagesService } from './pages.service';
import { REGION_SOURCES, RegionName } from './report-definitions';

/** HTTP surface of the generic page layer. The web tier calls it server-side with the session token. */
type FormBody = { checksum?: unknown; values?: Record<string, unknown> };

function values(body: FormBody | undefined): Record<string, unknown> {
  const v = body?.values;
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw errors.invalidInput('values must be an object.');
  return v;
}

function asList(v: unknown): string[] {
  if (v === undefined) return [];
  return (Array.isArray(v) ? v : [v]).map(String);
}

@Controller()
export class PagesController {
  constructor(private readonly pages: PagesService, @Inject(AUTH_CONFIG) private readonly auth: AuthConfig) {}

  @Get('session')
  async me(@Actor() actor: Principal) {
    return { ...(await this.pages.me(actor)), authMode: this.auth.mode };
  }

  /** IR / classic / cards regions: ?q=&sort=&dir=&page=&facet=ITEM:VALUE&all=1&item.<NAME>=value */
  @Get('regions/:name')
  region(@Actor() actor: Principal, @Param('name') name: string, @Query() q: Record<string, unknown>) {
    if (!Object.prototype.hasOwnProperty.call(REGION_SOURCES, name)) throw errors.invalidInput(`Region ${name} is not known.`);
    const facets: Record<string, string[]> = {};
    for (const f of asList(q.facet)) {
      const at = f.indexOf(':');
      if (at < 1) throw errors.invalidInput('facet must be ITEM:VALUE.');
      (facets[f.slice(0, at)] ??= []).push(f.slice(at + 1));
    }
    return this.pages.report(actor, name as RegionName, {
      search: typeof q.q === 'string' ? q.q : undefined,
      sort: typeof q.sort === 'string' ? q.sort : undefined,
      dir: typeof q.dir === 'string' ? q.dir : undefined,
      page: q.page === undefined ? 1 : Number(q.page),
      facets, all: q.all === '1',
    }, q);
  }

  @Get('lovs/:name')
  lov(@Actor() actor: Principal, @Param('name') name: string) {
    return this.pages.lov(actor, name);
  }

  /** New row: defaults, plus values the calling page passes (?column=value). */
  @Get('forms/:name')
  newRow(@Actor() actor: Principal, @Param('name') name: string, @Query() q: Record<string, unknown>) {
    return this.pages.formGet(actor, name, null, q);
  }

  @Get('forms/:name/:id')
  getRow(@Actor() actor: Principal, @Param('name') name: string, @Param('id') id: string) {
    return this.pages.formGet(actor, name, id);
  }

  @Post('forms/:name')
  create(@Actor() actor: Principal, @Param('name') name: string, @Body() body: FormBody) {
    return this.pages.formCreate(actor, name, values(body));
  }

  @Put('forms/:name/:id')
  save(@Actor() actor: Principal, @Param('name') name: string, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.formUpdate(actor, name, id, body?.checksum, values(body));
  }

  @Delete('forms/:name/:id')
  remove(@Actor() actor: Principal, @Param('name') name: string, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.formDelete(actor, name, id, body?.checksum);
  }
}
