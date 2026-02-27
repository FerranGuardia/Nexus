"""Auto-discover and import all recipe modules in this package."""

import importlib
import pkgutil
import sys


def _load_all():
    """Import (or reload) all sibling modules to trigger @recipe registration.

    Only reloads modules that were already imported (i.e., on server restart).
    Fresh imports don't need reload, saving 11 redundant import operations.
    """
    package_path = __path__
    for _importer, module_name, _is_pkg in pkgutil.iter_modules(package_path):
        if module_name.startswith("_"):
            continue
        try:
            full = f"{__name__}.{module_name}"
            already_loaded = full in sys.modules
            mod = importlib.import_module(full)
            # Only reload if it was already imported (handles server restart / test reload)
            if already_loaded:
                importlib.reload(mod)
        except Exception:
            pass  # Broken recipe file should never crash the system


_load_all()
