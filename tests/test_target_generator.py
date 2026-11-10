import hashlib
import json
import pytest

from apex2next_extractor.generator import generate_project


def _ir():
    return {
        "irVersion": "1.0.0",
        "application": {"id": "app:demo", "name": "Demo & Orders", "sourceFormat": "APEXLANG"},
        "objects": [
            {"id": "page:10", "type": "PAGE", "sourceType": "page", "name": "Orders / Review",
             "properties": {}, "source": {"file": "pages/p10.apx", "line": 1}},
            {"id": "process:10", "type": "PROCESS", "sourceType": "process", "name": "Save order",
             "properties": {"source": {"valueType": "PL_SQL_EXPRESSION", "rawExpression": "BEGIN NULL; END;",
               "expressionLanguage": "PL_SQL", "classificationConfidence": "HIGH", "preserved": True}},
             "source": {"file": "pages/p10.apx", "line": 4}},
            {"id": "plugin:1", "type": "PLUGIN", "sourceType": "plugin", "name": "Chart plugin",
             "properties": {}, "source": {"file": "pages/p10.apx", "line": 8}},
            {"id": "item:10", "type": "ITEM", "sourceType": "page_item", "name": "Order Number",
             "parentId": "page:10", "properties": {}, "source": {"file": "pages/p10.apx", "line": 3}},
        ],
        "relationships": [], "references": [], "dependencies": [], "diagnostics": [],
        "metadata": {"sourceHash": "sha256:demo", "adapterVersion": "0.1.0"},
    }


def test_generator_emits_workspace_and_review_artifacts(tmp_path):
    result = generate_project(_ir(), tmp_path / "generated")
    root = tmp_path / "generated"
    route = "orders-review-" + hashlib.sha256(b"page:10").hexdigest()[:8]
    expected = ["apps/web/app/page.tsx", "apps/web/app/layout.tsx",
        f"apps/web/app/pages/{route}/page.tsx", "apps/api/src/main.ts",
        "apps/api/src/health.controller.ts", "apps/api/src/auth/auth.service.ts",
        "apps/api/src/auth/authorization-review.guard.ts", "db/migrations/0001_baseline.sql",
        "migration-report/source-ir.json", "migration-report/semantic-analysis.json",
        "migration-report/manual-review.md", "generation-manifest.json"]
    for relative in expected:
        assert (root / relative).is_file(), relative
    assert result["pageCount"] == 1
    report = json.loads((root / "migration-report/summary.json").read_text())
    assert report["generatedBusinessSchema"] is False
    assert report["generatedBusinessLogic"] is False
    page = (root / f"apps/web/app/pages/{route}/page.tsx").read_text()
    assert "Orders / Review" in page
    assert "BEGIN NULL; END;" not in page
    assert "GeneratedPageInventory" in page
    assert any((root / "apps/api/src/dto").glob("*.dto.ts"))
    assert any((root / "apps/api/src/processes").glob("*.service.ts"))
    assert (root / "apps/api/test/generated-scaffold.test.js").is_file()


def test_generation_is_deterministic(tmp_path):
    generate_project(_ir(), tmp_path / "first")
    generate_project(_ir(), tmp_path / "second")
    for path in sorted((tmp_path / "first").rglob("*")):
        if path.is_file():
            relative = path.relative_to(tmp_path / "first")
            assert path.read_bytes() == (tmp_path / "second" / relative).read_bytes()


def test_generator_refuses_non_empty_output_without_overwrite(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        generate_project(_ir(), target)
    assert (target / "keep.txt").read_text() == "keep"


def test_generator_rejects_invalid_ir_without_writing(tmp_path):
    invalid = _ir()
    invalid["application"].pop("id")
    target = tmp_path / "invalid"
    with pytest.raises(ValueError, match="Invalid Normalized IR"):
        generate_project(invalid, target)
    assert not target.exists()


def test_manifest_hashes_every_generated_file_except_itself(tmp_path):
    generate_project(_ir(), tmp_path / "generated")
    root = tmp_path / "generated"
    manifest = json.loads((root / "generation-manifest.json").read_text())
    assert manifest["fileCount"] == len(manifest["files"]) + 1
    for relative, digest in manifest["files"].items():
        assert digest == "sha256:" + hashlib.sha256((root / relative).read_bytes()).hexdigest()


def test_generator_emits_postgres_runtime_contract(tmp_path):
    generate_project(_ir(), tmp_path / "generated")
    root = tmp_path / "generated"
    expected = [
        "apps/api/src/database/postgres-database.ts",
        "apps/api/src/database/postgres-repository.ts",
        "apps/api/src/database/database.module.ts",
        "apps/api/src/database/database-health.service.ts",
        "apps/api/test/postgres.integration.test.js",
        "apps/api/scripts/migrate.mjs",
    ]
    for relative in expected:
        assert (root / relative).is_file(), relative
    database = (root / "apps/api/src/database/postgres-database.ts").read_text()
    repository = (root / "apps/api/src/database/postgres-repository.ts").read_text()
    assert "BEGIN" in database and "ROLLBACK" in database and "COMMIT" in database
    assert "VALUES (" in repository and "$1" in repository
    assert "Unknown or non-writable columns" in repository
    package = json.loads((root / "apps/api/package.json").read_text())
    assert "pg" in package["dependencies"]
    assert "@types/pg" in package["devDependencies"]
    assert "schema_migrations" in (root / "db/migrations/0001_baseline.sql").read_text()
    app_module = (root / "apps/api/src/app.module.ts").read_text()
    assert "DatabaseModule" in app_module and "imports:" in app_module
    database_module = (root / "apps/api/src/database/database.module.ts").read_text()
    assert "DatabaseHealthService" in database_module


def test_generator_postgres_runtime_is_deterministic(tmp_path):
    generate_project(_ir(), tmp_path / "first")
    generate_project(_ir(), tmp_path / "second")
    for path in sorted((tmp_path / "first").rglob("*")):
        if path.is_file():
            relative = path.relative_to(tmp_path / "first")
            assert path.read_bytes() == (tmp_path / "second" / relative).read_bytes()


def test_generator_integrates_r3_ui_metadata_and_inventory(tmp_path):
    generate_project(_ir(), tmp_path / "generated")
    root = tmp_path / "generated"
    spec = (root / "apps/web/lib/apex2next-generated-spec.ts").read_text()
    page = (root / f"apps/web/app/pages/orders-review-{hashlib.sha256(b'page:10').hexdigest()[:8]}/page.tsx").read_text()
    report = json.loads((root / "migration-report/ui-generation.json").read_text())
    assert "GENERATED_UI_SPEC" in spec
    assert "GeneratedPageInventory" in page
    assert report["pageCount"] == 1
    assert report["componentCount"] == 1
