"""Static Oracle metadata inventory, conversion, and data migration primitives."""
from .data_migration import ChunkCheckpointStore, build_chunk_manifest, load_manifest, run_migration
from .cutover_readiness import assess_cutover_readiness
from .data_reconciliation import reconcile_snapshots
from .ddl_conversion import CONVERTER_VERSION, convert_oracle_ddl
from .inventory import analyze_ddl
from .metadata_manifest import build_manifest, reconcile_manifest
from .pilot_qualification import assess_pilot
from .plsql_workbench import RULE_REGISTRY_VERSION, analyze_plsql, rule_registry
from .schema_plan import build_schema_plan
from .schema_plan import rule_registry as schema_rule_registry

__all__ = [
    "ChunkCheckpointStore", "CONVERTER_VERSION", "RULE_REGISTRY_VERSION",
    "assess_cutover_readiness", "analyze_ddl", "analyze_plsql", "build_chunk_manifest", "assess_pilot", "build_manifest",
    "build_schema_plan", "convert_oracle_ddl", "load_manifest", "reconcile_manifest",
    "reconcile_snapshots", "rule_registry", "run_migration", "schema_rule_registry",
]
