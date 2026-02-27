"""Auto-discover and import all recipe modules in this package."""

import importlib
import pkgutil


def _load_all():
    """Import (or reload) all sibling modules to trigger @recipe registration."""
    package_path = __path__
    for _importer, module_name, _is_pkg in pkgutil.iter_modules(package_path):
        if module_name.startswith("_"):
            continue
        try:
            full = f"{__name__}.{module_name}"
            mod = importlib.import_module(full)
            # Reload ensures decorators re-fire after registry clear (tests, server restart)
            importlib.reload(mod)
        except Exception:
            pass  # Broken recipe file should never crash the system


_load_all()
