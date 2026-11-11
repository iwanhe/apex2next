# Generation report: Demo Permintaan Barang

Written by `apex2next generate`. It lists what the generator produced and what a developer still has to do.

## Summary

| | Generated | Provided | Manual | Not applicable |
|---|---|---|---|---|
| Pages | 15 | 1 | 2 | 1 |
| Regions | 11 | 0 | 3 | 0 |
| Lovs | 5 | 3 | 0 | 0 |

Generated files: 22. Open items: 19 ASSISTED, 32 MANUAL.

## Pages

| Page | Name | Pattern | Status | Files | Open items |
|---|---|---|---|---|---|
| 0 | Global Page | GLOBAL | NOT_APPLICABLE | 0 | - |
| 100 | Home | MANUAL | MANUAL | 0 | GEN001×1 |
| 190 | Approval Inbox | IR_PAGE | GENERATED | 1 | GEN011×1 |
| 191 | Approval | FORM_DIALOG | GENERATED | 1 | GEN006×2, GEN008×2, GEN011×1 |
| 200 | Departments | IR_PAGE | GENERATED | 1 | GEN011×1 |
| 201 | Department | FORM_DIALOG | GENERATED | 2 | GEN009×1, GEN011×1 |
| 210 | Items | FACETED_CARDS | GENERATED | 1 | GEN011×1, GEN012×1 |
| 211 | Item | FORM_DIALOG | GENERATED | 2 | GEN009×1, GEN011×1 |
| 300 | Permintaan Barang | FACETED_REPORT | GENERATED | 1 | GEN011×1, GEN012×1 |
| 301 | Permintaan Barang | FORM_DIALOG | GENERATED | 2 | GEN006×1, GEN007×1, GEN008×7, GEN009×1, GEN011×1 |
| 302 | Detail Permintaan | MANUAL | MANUAL | 0 | GEN001×1, GEN008×3, GEN011×3 |
| 310 | Baris Permintaan | IR_PAGE | GENERATED | 1 | GEN011×1 |
| 311 | Baris Permintaan | FORM_DIALOG | GENERATED | 2 | GEN009×1, GEN011×1 |
| 400 | Rekap Permintaan | IR_PAGE | GENERATED | 1 | - |
| 500 | Users & Roles | IR_PAGE | GENERATED | 1 | GEN011×1 |
| 501 | User Role | FORM_DIALOG | GENERATED | 2 | GEN009×1, GEN011×1 |
| 510 | Document Types & Approval | IR_PAGE | GENERATED | 1 | GEN011×1 |
| 511 | Document Type | FORM_DIALOG | GENERATED | 1 | GEN009×1, GEN011×1 |
| 9999 | Login Page | LOGIN | PROVIDED | 0 | - |

## Regions

| Page | Region | Kind | Status | Findings |
|---|---|---|---|---|
| 100 | Nilai per Department | NATIVE_JET_CHART | MANUAL | GEN002 |
| 100 | Permintaan per Status | NATIVE_JET_CHART | MANUAL | GEN002 |
| 100 | Ringkasan | TMPL_THEME_42$METRIC_CARD | MANUAL | GEN002 |
| 190 | Approval Inbox | IR | GENERATED | RGN006 |
| 200 | Departments | IR | GENERATED | RGN006 |
| 210 | Hasil Items | CARDS | GENERATED | RGN006 |
| 300 | Hasil Permintaan Barang | CLASSIC | GENERATED | RGN006 |
| 302 | Baris Permintaan | CLASSIC | GENERATED | RGN002, RGN006 |
| 302 | Daftar Permintaan Barang | CLASSIC | GENERATED | RGN006 |
| 302 | Permintaan Barang | CLASSIC | GENERATED | RGN002, RGN006 |
| 310 | Baris Permintaan | IR | GENERATED | RGN006 |
| 400 | Rekap Permintaan | IR | GENERATED | RGN006 |
| 500 | Users & Roles | IR | GENERATED | RGN006 |
| 510 | Document Types & Approval | IR | GENERATED | RGN006 |

## LOVs

| LOV | Status | Findings |
|---|---|---|
| APX_DEMO_DEPARTMENTS | GENERATED | EXP005, RGN006 |
| APX_DEMO_ITEMS | GENERATED | EXP005, RGN006 |
| APX_DEMO_REQUESTS | GENERATED | EXP005, RGN006 |
| APX_DEMO_REQUEST_LINES | GENERATED | RGN006 |
| DEMO_ROLES | GENERATED | EXP005, RGN006 |
| ITEMS_CATEGORY | PROVIDED | - |
| REQUESTS_STATUS | PROVIDED | - |
| YES_NO | PROVIDED | - |

## Open items (TODO)

| Where | Code | Disposition | What | Detail |
|---|---|---|---|---|
| page 100 | GEN001 | MANUAL | Page matches no supported pattern; write the page by hand. | regions: NATIVE_JET_CHART, TMPL_THEME_42$METRIC_CARD |
| page 190 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 191 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | button APPROVE |
| page 191 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | button REJECT |
| page 191 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 191 | GEN006 | MANUAL | Business logic: PL/SQL process to implement in a page service. | CALL_APPROVE |
| page 191 | GEN006 | MANUAL | Business logic: PL/SQL process to implement in a page service. | CALL_REJECT |
| page 200 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 201 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 201 | GEN009 | MANUAL | Form DML to wire to a business service (create, update, delete). | SAVE_DEPARTMENTS |
| page 210 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 210 | GEN012 | ASSISTED | Static content region is not rendered by the generated page. | Items |
| page 211 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 211 | GEN009 | MANUAL | Form DML to wire to a business service (create, update, delete). | SAVE_ITEMS |
| page 300 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 300 | GEN012 | ASSISTED | Static content region is not rendered by the generated page. | Permintaan Barang |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | button DELETE |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | button SAVE |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | button SUBMIT |
| page 301 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | read-only P301_DEPARTMENT_ID |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | read-only P301_NEED_DATE |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | read-only P301_PURPOSE |
| page 301 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | read-only P301_STATUS |
| page 301 | GEN006 | MANUAL | Business logic: PL/SQL process to implement in a page service. | CALL_SUBMIT_REQUESTS |
| page 301 | GEN009 | MANUAL | Form DML to wire to a business service (create, update, delete). | SAVE_REQUESTS |
| page 301 | GEN007 | MANUAL | Validation to implement in a page service. | NEED_DATE_AFTER_REQUEST_DATE |
| page 302 | GEN001 | MANUAL | Page matches no supported pattern; write the page by hand. | regions: 3 classic report(s) |
| page 302 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | button CREATE_REQUEST_LINES |
| page 302 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_HEADER |
| page 302 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REQUEST_LINES |
| page 302 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REQUEST_LINES |
| page 302 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | display condition Belum dipilih |
| page 302 | GEN008 | MANUAL | Server-side condition (button, read-only, display) to implement in a page service. | display condition Permintaan Barang |
| page 310 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 311 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 311 | GEN009 | MANUAL | Form DML to wire to a business service (create, update, delete). | SAVE_REQUEST_LINES |
| page 500 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 501 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 501 | GEN009 | MANUAL | Form DML to wire to a business service (create, update, delete). | SAVE_USER_ROLE |
| page 510 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_DIALOG_CLOSED_REFRESH_REPORT |
| page 511 | GEN011 | ASSISTED | Dynamic action: behaviour is provided by the runtime for dialogs and refresh; review others. | ON_CLICK_CANCEL_CLOSE_DIALOG |
| page 511 | GEN009 | MANUAL | Form DML to wire to a business service (create, update, delete). | SAVE_DOCUMENT_TYPE |
| page 100, Nilai per Department | GEN002 | MANUAL | Region type has no generator; write the region by hand. | NATIVE_JET_CHART |
| page 100, Permintaan per Status | GEN002 | MANUAL | Region type has no generator; write the region by hand. | NATIVE_JET_CHART |
| page 100, Ringkasan | GEN002 | MANUAL | Region type has no generator; write the region by hand. | TMPL_THEME_42$METRIC_CARD |
| authorization | GEN010 | MANUAL | Authorization scheme to implement in the security service. | ADMIN_RIGHTS |
| authorization | GEN010 | MANUAL | Authorization scheme to implement in the security service. | APP_USERS |
| authorization | GEN010 | MANUAL | Authorization scheme to implement in the security service. | MASTER_DATA |
| authorization | GEN010 | MANUAL | Authorization scheme to implement in the security service. | REQUESTER |
| authorization | GEN010 | MANUAL | Authorization scheme to implement in the security service. | WAREHOUSE |

## Finding codes

`GEN` codes are defined by the generator, `RGN` by the region SQL translator and `EXP` by the expression converter of the schema plan. ASSISTED means generated and to be reviewed; MANUAL means not generated.
