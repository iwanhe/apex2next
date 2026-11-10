import { bindUiSpec } from '@apex2next/runtime-api';
import { UI_SPEC } from './ui-spec.generated';

/**
 * Form runtime of @apex2next/runtime-api bound to this application's generated UI spec. The page services use
 * these names unchanged since the extraction (roadmap R2).
 */
export {
  DML_MESSAGES, changed, checksum, fetchForm, lockForChange, validateItems, writableItems,
} from '@apex2next/runtime-api';
export type { FormDef, FormItem, SubmitResult } from '@apex2next/runtime-api';
export const { formDef, result } = bindUiSpec(UI_SPEC);
