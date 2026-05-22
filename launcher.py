"""Frozen-mode entry point.

PyInstaller can't bootstrap `pokemon_buddy/__main__.py` directly because
that file uses `from .app import main` — relative imports require a
package context that PyInstaller's launcher doesn't provide. This script
uses the absolute path and is what the spec file points at.

`python -m pokemon_buddy` still works via `__main__.py` for development.
"""

from pokemon_buddy.app import main

if __name__ == "__main__":
    raise SystemExit(main())
