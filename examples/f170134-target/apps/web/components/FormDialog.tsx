import { apiGet, type FormResponse } from '../lib/api';
import { cancelLabel, formButtons, formFields, postedColumns } from '../lib/forms';
import { apiErrorOnly } from '../lib/guard';
import { page } from '../lib/spec';
import { ApexForm } from './ApexForm';
import { ErrorRegion } from './Alerts';
import { Dialog } from './Dialog';

/**
 * Modal form page: NATIVE_FORM_INIT through the API (values, checksum, button conditions, read-only state),
 * items and buttons from the export, submit through the bound server action, then back to the parent page.
 */
export async function FormDialog(props: {
  pageId: number; form: string; id: string | null; load: string; returnTo: string;
  flash?: Record<string, string>; extraItems?: Record<string, { column: string }>;
}) {
  const p = page(props.pageId);
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
  const fields = await formFields(props.pageId, data.values, data.readOnly ?? {}, props.extraItems);
  return (
    <Dialog page={props.pageId} title={p.title} closeHref={props.returnTo}>
      <ApexForm
        binding={{ form: props.form, id: props.id, returnTo: props.returnTo, columns: postedColumns(fields), flash: props.flash }}
        fields={fields} values={data.values} checksum={data.checksum} buttons={formButtons(props.pageId, data.buttons)}
        cancelHref={props.returnTo} cancelLabel={cancelLabel(props.pageId)} />
    </Dialog>
  );
}
