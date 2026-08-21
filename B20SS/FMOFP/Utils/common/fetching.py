import os
import sys

def fetch():
    # Determine project root dynamically
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    sys.path.insert(0, project_root)
    fmofp_path = os.path.join(project_root, 'FMOFP')
    sys.path.insert(0, fmofp_path)

    # This module is imported (directly or transitively) by nearly
    # everything in the codebase very early on, which makes fetch()
    # the best available single choke point for installing the
    # dual-path import alias shim -- see Utils/dual_path_compat.py for
    # why this is needed. Installing it here (immediately after the
    # two sys.path entries above are in place) means both "import
    # Systems.X" and "from FMOFP.Systems.X import Y" resolve to the
    # same module/class objects for essentially every entry point in
    # this codebase, without needing to duplicate this call in each
    # one individually.
    try:
        from Utils.dual_path_compat import install as _install_dual_path_alias
        _install_dual_path_alias()
    except ImportError:
        pass  # dual_path_compat not present (e.g. older checkout) -- degrade gracefully

def fetch_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def fetch_fmofp_path():
    return os.path.join(fetch_project_root(), 'FMOFP')

# Add project paths immediately when this module is imported
fetch()



# For debugging purposes
if __name__ == "__main__":
    print(f"Project root: {fetch_project_root()}")
    print(f"FMOFP path: {fetch_fmofp_path()}")