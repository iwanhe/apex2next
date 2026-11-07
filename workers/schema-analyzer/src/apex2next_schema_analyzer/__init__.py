"""Static Oracle metadata inventory and conservative PostgreSQL conversion."""

from .ddl_conversion import CONVERTER_VERSION, convert_oracle_ddl
from .inventory import analyze_ddl
from .metadata_manifest import build_manifest, reconcile_manifest

__all__ = [
    "analyze_ddl",
    "build_manifest",
    "convert_oracle_ddl",
    "CONVERTER_VERSION",
    "reconcile_manifest",
]
