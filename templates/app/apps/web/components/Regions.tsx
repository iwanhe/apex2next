// Binds the composed-page regions of @apex2next/runtime-web to this application (R4a).
import type { ComponentProps } from 'react';
import * as Rt from '@apex2next/runtime-web/components/Regions';
import { PageHeader as RtHeader } from '@apex2next/runtime-web/components/PageHeader';
import { APP } from '../lib/app';

export { ListRegion, StaticRegion } from '@apex2next/runtime-web/components/Regions';

type Bound<T extends (props: never) => unknown> = Omit<Parameters<T>[0], 'app'>;

export function PageHeader(props: Omit<ComponentProps<typeof RtHeader>, 'app'>) {
  return <RtHeader app={APP} {...props} />;
}
export function ReportRegion(props: Bound<typeof Rt.ReportRegion>) {
  return <Rt.ReportRegion app={APP} {...props} />;
}
export function IrRegion(props: Bound<typeof Rt.IrRegion>) {
  return <Rt.IrRegion app={APP} {...props} />;
}
export function CardsRegion(props: Bound<typeof Rt.CardsRegion>) {
  return <Rt.CardsRegion app={APP} {...props} />;
}
