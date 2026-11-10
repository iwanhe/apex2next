"""Static APEX source extraction and Normalized IR adapters."""

from .apex_export import extract_export
from .apexlang import extract_apexlang, parse_apexlang_text
from .apexlang_ast import (
    ApexLangAst,
    ApexLangDeclaration,
    ApexLangProperty,
    ApexLangToken,
    SourceSpan,
    parse_apexlang_ast,
    parse_apexlang_properties,
    tokenize_apexlang,
)
from .dependency_graph import analyze_dependency_graph
from .semantic_analysis import analyze_semantics
from .generator import GENERATOR_VERSION, generate_project
from .ui_generator import build_ui_spec
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
    "ApexLangAst",
    "ApexLangDeclaration",
    "ApexLangProperty",
    "ApexLangToken",
    "SourceSpan",
    "parse_apexlang_ast",
    "parse_apexlang_properties",
    "tokenize_apexlang",
    "adapt_apex_export",
    "adapt_apexlang_directory",
    "object_fingerprint",
    "stable_identity",
    "resolve_references",
    "analyze_dependency_graph",
    "analyze_semantics",
    "GENERATOR_VERSION",
    "generate_project",
    "build_ui_spec",
]
