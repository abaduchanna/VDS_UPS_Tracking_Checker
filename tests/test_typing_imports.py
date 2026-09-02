"""Regression: every name used in annotations must be imported/defined.

verge_ups_tracking_checker.py once used Optional/Callable/List/Dict in
function-signature annotations without importing them from typing. Signatures
are evaluated at import time, so the frozen EXE died instantly with:
    NameError: name 'Optional' is not defined  (line 174, in <module>)
This test AST-scans the app and fails if any annotation name is unresolved.
"""
import ast
import builtins
import os

APP = os.path.join(os.path.dirname(__file__), "..", "verge_ups_tracking_checker.py")

# Names provided by the interpreter at runtime, not present in dir(builtins)
RUNTIME_PROVIDED = {"__file__", "__name__", "__doc__"}


def _defined_names(tree):
    defined = set(dir(builtins)) | RUNTIME_PROVIDED
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    defined.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
    return defined


def test_annotations_only_use_defined_names():
    src = open(APP, encoding="utf-8").read()
    tree = ast.parse(src)
    defined = _defined_names(tree)
    missing = sorted({
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        and node.id not in defined
    })
    assert not missing, f"Names used but never defined/imported: {missing}"


def test_typing_names_imported_from_typing():
    """Direct guard for the shipped bug: Optional/Callable/List/Dict used
    in signatures must come from a typing import."""
    src = open(APP, encoding="utf-8").read()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            imported |= {a.asname or a.name for a in node.names}
    used = {
        n.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        and n.id in {"Optional", "Callable", "List", "Dict", "Tuple", "Any", "Union"}
    }
    assert used, "sanity: app should still use typing annotations"
    unresolved = used - imported
    assert not unresolved, f"typing names used without import: {unresolved}"
