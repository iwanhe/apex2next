# Examples

Store sanitized, synthetic APEX exports and Oracle object examples only. Never commit customer exports, credentials, production records, or licensed third-party plug-in source without permission.

The first pilot fixture should be a deliberately small CRUD application with a table, sequence/identity, validation, authorization, report, and one PL/SQL process.

## Contents

- [`f170134-target/`](f170134-target/README.md): WP9 pilot target for the owner-supplied demo application "Demo Permintaan Barang" (170134). It contains generated PostgreSQL migrations, reviewed business functions and hand-written NestJS business services. It contains no source export and no customer data. Test seed rows are the demo values from the application's own seed script.
