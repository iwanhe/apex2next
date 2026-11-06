"""Static APEX export metadata extraction (never executes exported PL/SQL)."""

from .apex_export import extract_export

__all__ = ["extract_export"]
