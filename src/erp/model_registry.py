import importlib
import pkgutil
from pathlib import Path

from erp.database.base import Base


def register_all_models(root_path: str, package_prefix: str) -> None:
    """
    Recursively finds and imports all 'models' modules.
    """
    for _loader, module_name, _is_pkg in pkgutil.walk_packages([root_path], package_prefix):
        # We want to catch:
        # 1. modules named 'models' (e.g., integrations.ebay.models)
        # 2. modules inside a 'models' package (e.g., api.models.supplier)
        if 'models' in module_name.split('.'):
            importlib.import_module(module_name)

# Define the absolute path to your 'src/erp' directory
ROOT_DIR = Path(__file__).parent
register_all_models(ROOT_DIR, "erp.")

# Export Base so Alembic can see the metadata
metadata = Base.metadata
