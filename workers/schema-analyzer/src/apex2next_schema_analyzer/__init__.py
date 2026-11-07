"""Static Oracle DDL inventory and conservative PostgreSQL conversion."""

from .ddl_conversion import CONVERTER_VERSION, convert_oracle_ddl
from .inventory import analyze_ddl

__all__ = ["analyze_ddl", "convert_oracle_ddl", "CONVERTER_VERSION"]
