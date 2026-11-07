"""Static APEX source extraction and Normalized IR adapters."""

from .apex_export import extract_export
from .apexlang import extract_apexlang, parse_apexlang_text
from .apexlang_ast import parse_apexlang_ast, tokenize_apexlang
from .normalized_ir import (
    adapt_apex_export,
    adapt_apexlang_directory,
    object_fingerprint,
    stable_identity,
    resolve_references,
)

__all__ = [
    "extract_export",
    "extract_apexlang",
    "parse_apexlang_text",
    "parse_apexlang_ast",
    "tokenize_apexlang",
    "adapt_apex_export",
    "adapt_apexlang_directory",
    "object_fingerprint",
    "stable_identity",
    "resolve_references",
]
