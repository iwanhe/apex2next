// Binds a shared component of @apex2next/runtime-web to this application (roadmap R2).
import type { ComponentProps } from 'react';
import { Shell as Rt } from '@apex2next/runtime-web/components/Shell';
import { APP } from '../lib/app';

export function Shell(props: Omit<ComponentProps<typeof Rt>, 'app'>) {
  return <Rt app={APP} {...props} />;
}
