"""
Dual sys.path import aliasing compatibility shim.

Background
----------
This codebase's various entry points (SystemStart.py, install.py, and
several files under Tests/) add BOTH the project root (B20SS/) and the
FMOFP/ directory itself to sys.path, so that two different import
spellings both work for the same code:

    import Systems.radarManagement.radar_enums          # "bare" -- resolves
                                                          # relative to FMOFP/
    from FMOFP.Systems.radarManagement.radar_enums import X  # "absolute" --
                                                          # resolves relative
                                                          # to B20SS/

The problem: Python's import system caches modules by their fully
qualified dotted name in sys.modules. "Systems.radarManagement.radar_enums"
and "FMOFP.Systems.radarManagement.radar_enums" are different dotted
names, so even though they point at the exact same file on disk, Python
loads and executes that file TWICE, producing two independent module
objects -- and, critically, two independent class objects for anything
defined in it. isinstance() checks, `is` identity comparisons, and
singleton patterns (a class checking `if cls._instance is None`) all
silently break across the two import spellings, because Python has no
way to know they're "the same" class/instance.

This was discovered and partially worked around (August 2026) by
consolidating three separately-defined copies of the radar mode enums
into one canonical file with the other two re-exporting it -- but that
only fixes the VALUE drift for that one specific case. The same
underlying double-load problem still affects any other class, in any
of the packages that get imported both ways (confirmed live: Utils is
bare-imported in 103 files and absolute-imported elsewhere; Systems in
15; core in 4; storage in 2; Interfaces in 1).

Fix
---
Install a sys.meta_path finder that intercepts bare imports of the
affected top-level packages and redirects them to resolve to the
already-loaded (or freshly-loaded-and-cached) FMOFP.<name> equivalent,
so that both spellings always return the literal same module object at
every level of the package hierarchy -- not just the top-level package,
but every submodule imported under it, recursively, without needing to
enumerate them in advance.

install() is idempotent and safe to call multiple times (from multiple
entry points, or if this module itself gets imported under both of its
own two possible spellings) -- it checks whether the finder is already
installed before adding it again.
"""

import sys
import importlib
import importlib.abc
import importlib.util

# Only alias top-level packages that are genuinely imported both ways
# somewhere in this codebase. Deliberately excludes Tests, MIL_STD_1553B,
# and local_messaging, which (as of this audit) are never bare-imported,
# so aliasing them would add risk for zero benefit.
ALIASED_ROOTS = frozenset({
    "Systems",
    "Utils",
    "Interfaces",
    "core",
    "storage",
})

_MARKER_ATTR = "_fmofp_dual_path_alias_finder"


class _AliasLoader(importlib.abc.Loader):
    """A loader that hands back an already-loaded module instead of
    creating and executing a new one. This is what makes `import Systems.X`
    resolve to the exact same object as `import FMOFP.Systems.X`."""

    def __init__(self, canonical_module):
        self._canonical_module = canonical_module

    def create_module(self, spec):
        return self._canonical_module

    def exec_module(self, module):
        # The canonical module has already been fully imported and
        # executed via the normal import machinery (that's how we got
        # a reference to it in the finder below) -- nothing to do here.
        pass


class _DualPathAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".", 1)[0]
        if root not in ALIASED_ROOTS:
            return None  # not one of ours -- defer to normal finders

        canonical_name = "FMOFP." + fullname
        try:
            canonical_module = importlib.import_module(canonical_name)
        except ImportError:
            # No FMOFP.<name> equivalent exists (e.g. a genuinely
            # bare-only module with no absolute counterpart) -- fall
            # through to normal import machinery for the bare name.
            return None

        return importlib.util.spec_from_loader(
            fullname, _AliasLoader(canonical_module)
        )


def install():
    """Install the dual-path alias finder, if not already installed."""
    for finder in sys.meta_path:
        if getattr(finder, _MARKER_ATTR, False):
            return  # already installed
    finder = _DualPathAliasFinder()
    setattr(finder, _MARKER_ATTR, True)
    # Insert at the front so it gets first refusal on the aliased root
    # names, before the standard PathFinder would load a second,
    # separate copy.
    sys.meta_path.insert(0, finder)
