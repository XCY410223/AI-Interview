"""全量导入 app 下所有模块：兜住占位模块 ImportError 并提升覆盖率。"""
import importlib
import pkgutil

import app


def _module_names():
    names = ["app"]
    names += [m.name for m in pkgutil.walk_packages(app.__path__, prefix="app.")]
    return names


def test_import_all_modules():
    names = _module_names()
    assert len(names) > 10
    for name in names:
        importlib.import_module(name)
