// Binds a shared component of @apex2next/runtime-web to this application (roadmap R2).
import type { ComponentProps } from 'react';
import { SuccessMessage as Rt } from '@apex2next/runtime-web/components/Alerts';
import { APP } from '../lib/app';

export { ErrorRegion } from '@apex2next/runtime-web/components/Alerts';
export function SuccessMessage(props: Omit<ComponentProps<typeof Rt>, 'app'>) {
  return <Rt app={APP} {...props} />;
}
