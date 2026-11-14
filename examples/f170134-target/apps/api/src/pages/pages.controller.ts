import { Body, Controller, Delete, Get, HttpCode, Inject, Param, Post, Put, Query, Req } from '@nestjs/common';
import type { Request } from 'express';
import { Actor, AllowDuringPasswordChange, AUTH_CONFIG, errors } from '@apex2next/runtime-api';
import type { AuthConfig, Principal } from '@apex2next/runtime-api';
import { MasterFormName, PagesService } from './pages.service';
import { REGION_SOURCES, RegionName } from './report-definitions';

/** HTTP surface of the WP9.5 page layer. The web tier calls it server-side with the session token. */
const MASTER: readonly MasterFormName[] = ['department', 'item', 'userRole'];

type FormBody = { checksum?: unknown; values?: Record<string, unknown> };

function values(body: FormBody | undefined): Record<string, unknown> {
  const v = body?.values;
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw errors.invalidInput('values wajib berupa object.');
  return v;
}

function asList(v: unknown): string[] {
  if (v === undefined) return [];
  return (Array.isArray(v) ? v : [v]).map(String);
}

@Controller()
export class PagesController {
  constructor(private readonly pages: PagesService, @Inject(AUTH_CONFIG) private readonly auth: AuthConfig) {}

  /** The signed-in user, evaluated authorization schemes and the account mode (local accounts can change their password). */
  // A temporary-password session may read its own session metadata to render the forced-change page.
  // This endpoint exposes no application data; all business routes remain blocked by SessionGuard.
  @AllowDuringPasswordChange()
  @Get('session')
  async me(@Actor() actor: Principal, @Req() req: Request & { mustChangePassword?: boolean }) {
    return { ...(await this.pages.me(actor)), authMode: this.auth.mode, mustChangePassword: req.mustChangePassword === true };
  }

  @Get('pages/100')
  home(@Actor() actor: Principal) {
    return this.pages.home(actor);
  }

  /** IR / classic / cards regions: ?q=&sort=&dir=&page=&facet=ITEM:VALUE (repeatable)&all=1 (download). */
  @Get('regions/:name')
  region(@Actor() actor: Principal, @Param('name') name: string, @Query() q: Record<string, unknown>) {
    if (!Object.prototype.hasOwnProperty.call(REGION_SOURCES, name)) throw errors.invalidInput(`Region ${name} tidak dikenal.`);
    const facets: Record<string, string[]> = {};
    for (const f of asList(q.facet)) {
      const at = f.indexOf(':');
      if (at < 1) throw errors.invalidInput('facet harus ITEM:VALUE.');
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

  @Get('pages/302')
  requestDetail(@Actor() actor: Principal, @Query('requestId') requestId?: string, @Query('page') page?: string) {
    return this.pages.requestDetail(actor, requestId ? requestId : null, page ? Number(page) : 1);
  }

  // ------------------------------------------------------------ page 191
  @Get('forms/approval/:id')
  approval(@Actor() actor: Principal, @Param('id') id: string) {
    return this.pages.approvalForm(actor, id);
  }

  @Post('forms/approval/:id/approve')
  @HttpCode(200)
  approve(@Actor() actor: Principal, @Param('id') id: string, @Body() body: { note?: unknown }) {
    return this.pages.act(actor, id, 'APPROVE', body?.note);
  }

  @Post('forms/approval/:id/reject')
  @HttpCode(200)
  reject(@Actor() actor: Principal, @Param('id') id: string, @Body() body: { note?: unknown }) {
    return this.pages.act(actor, id, 'REJECT', body?.note);
  }

  // ------------------------------------------------------------ page 301
  @Get('forms/request')
  newRequest(@Actor() actor: Principal) {
    return this.pages.requestGet(actor, null);
  }

  @Get('forms/request/:id')
  request(@Actor() actor: Principal, @Param('id') id: string) {
    return this.pages.requestGet(actor, id);
  }

  @Post('forms/request')
  createRequest(@Actor() actor: Principal, @Body() body: FormBody) {
    return this.pages.requestCreate(actor, values(body));
  }

  @Put('forms/request/:id')
  saveRequest(@Actor() actor: Principal, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.requestSave(actor, id, body?.checksum, values(body), false);
  }

  @Post('forms/request/:id/submit')
  @HttpCode(200)
  submitRequest(@Actor() actor: Principal, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.requestSave(actor, id, body?.checksum, values(body), true);
  }

  @Delete('forms/request/:id')
  deleteRequest(@Actor() actor: Principal, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.requestDelete(actor, id, body?.checksum);
  }

  // ------------------------------------------------------------ page 311
  @Get('forms/requestLine')
  newLine(@Actor() actor: Principal, @Query('request_id') requestId?: string) {
    return this.pages.formGet(actor, 'requestLine', null, requestId ? { request_id: requestId } : {});
  }

  @Get('forms/requestLine/:id')
  line(@Actor() actor: Principal, @Param('id') id: string) {
    return this.pages.formGet(actor, 'requestLine', id);
  }

  @Post('forms/requestLine')
  createLine(@Actor() actor: Principal, @Body() body: FormBody) {
    return this.pages.lineCreate(actor, values(body));
  }

  @Put('forms/requestLine/:id')
  saveLine(@Actor() actor: Principal, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.lineUpdate(actor, id, body?.checksum, values(body));
  }

  @Delete('forms/requestLine/:id')
  deleteLine(@Actor() actor: Principal, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.lineDelete(actor, id, body?.checksum);
  }

  // ------------------------------------------------------------ page 511
  @Get('forms/docType/:id')
  docType(@Actor() actor: Principal, @Param('id') id: string) {
    return this.pages.formGet(actor, 'docType', id);
  }

  @Put('forms/docType/:id')
  saveDocType(@Actor() actor: Principal, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.docTypeUpdate(actor, id, body?.checksum, values(body));
  }

  // ------------------------------------------------------------ pages 201 / 211 / 501
  private master(name: string): MasterFormName {
    if (!(MASTER as readonly string[]).includes(name)) throw errors.invalidInput(`Form ${name} tidak dikenal.`);
    return name as MasterFormName;
  }

  @Get('forms/:name')
  newMaster(@Actor() actor: Principal, @Param('name') name: string) {
    return this.pages.formGet(actor, this.master(name), null);
  }

  @Get('forms/:name/:id')
  getMaster(@Actor() actor: Principal, @Param('name') name: string, @Param('id') id: string) {
    return this.pages.formGet(actor, this.master(name), id);
  }

  @Post('forms/:name')
  createMaster(@Actor() actor: Principal, @Param('name') name: string, @Body() body: FormBody) {
    return this.pages.masterCreate(actor, this.master(name), values(body));
  }

  @Put('forms/:name/:id')
  saveMaster(@Actor() actor: Principal, @Param('name') name: string, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.masterUpdate(actor, this.master(name), id, body?.checksum, values(body));
  }

  @Delete('forms/:name/:id')
  deleteMaster(@Actor() actor: Principal, @Param('name') name: string, @Param('id') id: string, @Body() body: FormBody) {
    return this.pages.masterDelete(actor, this.master(name), id, body?.checksum);
  }
}
