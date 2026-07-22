"""Test bootstrap.

Load ``client.py`` and ``const.py`` in isolation, under a synthetic package,
so the real ``o2cloud/__init__.py`` (which imports Home Assistant) is never
executed. This lets the client tests run in a plain Python environment.
"""

import importlib.util
import sys
import types
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "o2cloud"
_PKG_NAME = "o2pkg"

_pkg = types.ModuleType(_PKG_NAME)
_pkg.__path__ = [str(_PKG_DIR)]
sys.modules[_PKG_NAME] = _pkg


def _load(module_name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{_PKG_NAME}.{module_name}", _PKG_DIR / f"{module_name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Order matters: client.py does ``from .const import ...``.
_load("const")
_load("client")
