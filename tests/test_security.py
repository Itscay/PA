"""Security guard-rail test (BUILD_PLAN §10): no shell/eval/exec in assistant/."""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "assistant"

BANNED_CALLS = {"eval", "exec", "compile"}
BANNED_ATTRS = {"system", "popen"}  # os.system, os.popen
BANNED_SUBPROCESS_KW = "shell"  # keyword arg; value must never be True
BANNED_MODULES = {"pickle"}  # deserialising untrusted data = code execution risk


def _py_files() -> list[Path]:
    return sorted(PKG.rglob("*.py"))


def test_no_shell_or_eval_in_package() -> None:
    assert _py_files(), "assistant/ package not found"
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # plain eval/exec/compile(...)
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in BANNED_CALLS, f"{path}: {node.func.id}() banned"
                # subprocess given a shell string
                for kw in node.keywords:
                    if kw.arg == BANNED_SUBPROCESS_KW:
                        assert not (
                            isinstance(kw.value, ast.Constant) and kw.value.value is True
                        ), f"{path}: {BANNED_SUBPROCESS_KW} kwarg with True banned"
                # os.system / os.popen
                if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_ATTRS:
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                        raise AssertionError(f"{path}: os.{node.func.attr}() banned")


def test_no_banned_imports() -> None:
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in BANNED_MODULES, f"{path}: import {alias.name} banned"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                assert root not in BANNED_MODULES, f"{path}: from {node.module} banned"


def test_no_subprocess_shell_true_even_in_tests_dir() -> None:
    """The whole repo (not just the package) must not request a shell string."""
    banned = "shell" + "=True"  # assembled so this file doesn't trip its own check
    repo = Path(__file__).resolve().parent.parent
    for path in repo.rglob("*.py"):
        if ".venv" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        assert banned not in src, f"{path}: {banned} banned"
