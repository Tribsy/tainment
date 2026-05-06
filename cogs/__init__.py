"""
cogs package — Phase 0 extension-path indirection.

Discord.py loads each extension via a dotted import path. Phase 0 introduces
this `cogs` package so `EXTENSIONS = ['cogs.economy', ...]` works while the
actual cog source files still live at the repo root. Each `cogs/<name>.py`
in this package is a thin shim that re-exports `setup()` from the root-level
module of the same name.

Phase 1+ migrates the real code into `cogs/<domain>/` packages and deletes
the shims. The dotted-path API stays stable across both phases.
"""
