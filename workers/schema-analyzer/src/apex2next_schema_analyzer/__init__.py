"""Static Oracle metadata inventory, conversion, and data migration primitives."""

from .data_migration import (
    ChunkCheckpointStore,
    build_chunk_manifest,
    load_manifest,
    run_migration,
)
from .ddl_conversion import CONVERTER_VERSION, convert_oracle_ddl
from .inventory import analyze_ddl
from .metadata_manifest import build_manifest, reconcile_manifest

__all__ = [
    "ChunkCheckpointStore",
    "CONVERTER_VERSION",
    "analyze_ddl",
    "build_chunk_manifest",
    "build_manifest",
    "convert_oracle_ddl",
    "load_manifest",
    "reconcile_manifest",
    "run_migration",
]
