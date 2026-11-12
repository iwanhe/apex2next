-- APEX2NEXT WP9.2 — partial PostgreSQL DDL draft
-- Source install.sql SHA-256:
-- 7c71e9c56b76d5fe893d2f357e692b9e7c458adc37791784379842ec1712d66d
-- Only 3 tables without Oracle IDENTITY / virtual generated columns.
-- NOT a complete schema and NOT approved for deployment. No SQL was executed.
-- Review schema owner, identifier casing, collation, precision, defaults,
-- grants, dictionary evidence and data semantics before any rehearsal.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.apx_demo_roles (
    role_code   varchar(30)  NOT NULL,
    role_name   varchar(100) NOT NULL,
    description varchar(400),
    CONSTRAINT apx_demo_roles_pk PRIMARY KEY (role_code)
);

CREATE TABLE app.apx_demo_doc_types (
    doc_type       varchar(10)   NOT NULL,
    doc_name       varchar(100)  NOT NULL,
    prefix         varchar(10)   NOT NULL,
    table_name     varchar(128)  NOT NULL,
    pk_column      varchar(128)  NOT NULL,
    number_column  varchar(128)  NOT NULL,
    status_column  varchar(128)  DEFAULT 'STATUS' NOT NULL,
    amount_expr    varchar(4000),
    validate_proc  varchar(261),
    approver1_role varchar(30),
    approver2_role varchar(30),
    level2_limit   numeric       DEFAULT 0 NOT NULL,
    CONSTRAINT apx_demo_doc_types_pk PRIMARY KEY (doc_type),
    CONSTRAINT apx_demo_doc_types_fk1 FOREIGN KEY (approver1_role)
        REFERENCES app.apx_demo_roles (role_code),
    CONSTRAINT apx_demo_doc_types_fk2 FOREIGN KEY (approver2_role)
        REFERENCES app.apx_demo_roles (role_code)
);

CREATE TABLE app.apx_demo_doc_seq (
    doc_type varchar(10) NOT NULL,
    period   varchar(4)  NOT NULL,
    last_no  numeric    DEFAULT 0 NOT NULL,
    CONSTRAINT apx_demo_doc_seq_pk PRIMARY KEY (doc_type, period)
);

-- Intentionally excluded: six identity-bearing tables; REQUEST_LINES.LINE_AMOUNT
-- virtual generated column; all 8 CHECK predicates; three ALTER TABLE FKs;
-- four explicit indexes; 10 views; 4 PL/SQL packages; 5 triggers; grants;
-- configuration/demo seed DML. This partial draft is not a deployable pilot.
