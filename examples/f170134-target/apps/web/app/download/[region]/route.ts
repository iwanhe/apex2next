import { type NextRequest } from 'next/server';
import { downloadRegion } from '@apex2next/runtime-web/download';
import { IR_DOWNLOADS } from '../../../lib/app-routes.generated';

/** Interactive Report download (CSV / HTML) of the regions listed in the generated IR_DOWNLOADS. */
export async function GET(req: NextRequest, ctx: { params: Promise<{ region: string }> }) {
  const { region } = await ctx.params;
  return downloadRegion(req, region, IR_DOWNLOADS);
}
