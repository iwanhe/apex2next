import { apiGet, type FormResponse } from '../api';
import type { AppRuntime } from '../app';
import { cancelLabel, formButtons, formFields, postedColumns } from '../forms';
import { apiErrorOnly } from '../guard';
import { ApexForm } from './ApexForm';
import { ErrorRegion } from './Alerts';
import { Dialog } from './Dialog';

/**
 * Modal form page: NATIVE_FORM_INIT through the API (values, checksum, button conditions, read-only state),
 * items and buttons from the export, submit through the bound server action, then back to the parent page.
 */
export async function FormDialog(props: {
  app: AppRuntime;
  pageId: number; form: string; id: string | null; load: string; returnTo: string;
  extraItems?: Record<string, { column: string }>;
}) {
  const { spec } = props.app;
  const p = spec.page(props.pageId);
  let data: FormResponse;
  try {
    data = await apiGet<FormResponse>(props.load);
  } catch (e) {
    return (
      <Dialog page={props.pageId} title={p.title} closeHref={props.returnTo}>
        <div className="dialog-body"><ErrorRegion error={apiErrorOnly(e)} /></div>
      </Dialog>
    );
  }
  const fields = await formFields(spec, props.pageId, data.values, data.readOnly ?? {}, props.extraItems);
  return (
    <Dialog page={props.pageId} title={p.title} closeHref={props.returnTo}>
      <ApexForm submit={props.app.submit}
        binding={{ form: props.form, id: props.id, returnTo: props.returnTo, columns: postedColumns(fields) }}
        fields={fields} values={data.values} checksum={data.checksum} buttons={formButtons(spec, props.pageId, data.buttons)}
        cancelHref={props.returnTo} cancelLabel={cancelLabel(spec, props.pageId)} />
    </Dialog>
  );
}
