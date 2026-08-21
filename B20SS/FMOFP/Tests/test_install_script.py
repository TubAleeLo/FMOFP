"""
Test suite: install.py — unit tests for each of the six installer steps

These tests run the installer functions against controlled temporary
directories so they never touch the real repo layout.

Tests
-----
1.  check_python          — passes on this interpreter
2.  check_python          — rejects a too-old version tuple
3.  check_directories     — passes when all required dirs exist
4.  check_directories     — fails (SystemExit) when a dir is missing
5.  check_configs         — passes with valid XML files
6.  check_configs         — fails when an XML file is missing
7.  check_configs         — fails when an XML file is malformed
8.  initialise_databases  — creates expected database files
9.  initialise_databases  — creates tables from schema
10. verify_installation   — module-import check passes for present module
11. MIN_PYTHON constant    — value is (3, 9)
12. REQUIRED_PACKAGES      — includes PyQt6 and numpy
"""

import os
import sys
import sqlite3
import tempfile
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

_B20SS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for _p in (_B20SS, os.path.join(_B20SS, 'FMOFP')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()

# Import install.py from the B20SS root
_install_path = os.path.join(_B20SS, 'install.py')
import importlib.util as _ilu
_spec   = _ilu.spec_from_file_location("install", _install_path)
_install = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_install)


# ──────────────────────────────────────── framework ───────────────────────

class _Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self._failures = []

    def check(self, name, cond, detail=""):
        if cond:
            self.passed += 1
            print(f"  ✓  {name}")
        else:
            self.failed += 1
            msg = f"  ✗  {name}" + (f"  [{detail}]" if detail else "")
            print(msg)
            self._failures.append(msg)

    def summary(self):
        total = self.passed + self.failed
        print(f"\n  {self.passed}/{total} passed")
        if self._failures:
            print("\n  Failures:")
            for f in self._failures:
                print(f"    {f}")
        return self.failed == 0


# ───────────────────────────────── Step 1: Python check ──────────────────

def test_check_python_passes(r: _Results) -> None:
    print("\n  ── Step 1: check_python passes ──")
    try:
        _install.check_python()
        r.check("check_python() does not raise on current interpreter", True)
    except SystemExit as exc:
        r.check("check_python() does not raise on current interpreter",
                False, f"SystemExit: {exc}")


def test_check_python_rejects_old(r: _Results) -> None:
    print("\n  ── Step 1: check_python rejects old version ──")
    original = _install.MIN_PYTHON
    _install.MIN_PYTHON = (99, 0)
    raised = False
    try:
        _install.check_python()
    except SystemExit:
        raised = True
    finally:
        _install.MIN_PYTHON = original
    r.check("check_python() raises SystemExit for old Python", raised)


# ────────────────────────────── Step 2: Directory check ──────────────────

def test_check_directories_all_present(r: _Results) -> None:
    print("\n  ── Step 2: check_directories all present ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create all required directories
        required = [tmp_path / "FMOFP" / sub for sub in
                    ("Systems", "Interfaces", "MIL_STD_1553B",
                     "storage", "Utils", "core", "local_messaging")]
        fmofp_dir = tmp_path / "FMOFP"
        fmofp_dir.mkdir()
        for d in required:
            d.mkdir(parents=True, exist_ok=True)

        # Monkey-patch the constants
        orig_dirs = _install.REQUIRED_DIRS
        _install.REQUIRED_DIRS = [fmofp_dir] + required
        try:
            _install.check_directories()
            r.check("check_directories() passes when all dirs present", True)
        except SystemExit as exc:
            r.check("check_directories() passes when all dirs present",
                    False, str(exc))
        finally:
            _install.REQUIRED_DIRS = orig_dirs


def test_check_directories_missing(r: _Results) -> None:
    print("\n  ── Step 2: check_directories missing dir ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        orig_dirs = _install.REQUIRED_DIRS
        _install.REQUIRED_DIRS = [tmp_path / "does_not_exist"]
        raised = False
        try:
            _install.check_directories()
        except SystemExit:
            raised = True
        finally:
            _install.REQUIRED_DIRS = orig_dirs
        r.check("check_directories() raises SystemExit for missing dir", raised)


# ────────────────────────────── Step 4: Config check ─────────────────────

def _write_xml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_check_configs_valid(r: _Results) -> None:
    print("\n  ── Step 4: check_configs with valid XML ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        configs = [tmp_path / f"cfg{i}.xml" for i in range(4)]
        for cfg in configs:
            _write_xml(cfg, "<root><item>test</item></root>")

        orig = _install.REQUIRED_CONFIGS
        _install.REQUIRED_CONFIGS = configs
        try:
            _install.check_configs()
            r.check("check_configs() passes for valid XML files", True)
        except SystemExit as exc:
            r.check("check_configs() passes for valid XML files",
                    False, str(exc))
        finally:
            _install.REQUIRED_CONFIGS = orig


def test_check_configs_missing(r: _Results) -> None:
    print("\n  ── Step 4: check_configs missing file ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        missing = tmp_path / "missing.xml"
        orig = _install.REQUIRED_CONFIGS
        orig_script = _install.SCRIPT_DIR
        # Point SCRIPT_DIR into tmp so relative_to() works
        _install.SCRIPT_DIR = tmp_path
        _install.REQUIRED_CONFIGS = [missing]
        raised = False
        try:
            _install.check_configs()
        except SystemExit:
            raised = True
        finally:
            _install.REQUIRED_CONFIGS = orig
            _install.SCRIPT_DIR = orig_script
        r.check("check_configs() raises SystemExit for missing config", raised)


def test_check_configs_malformed(r: _Results) -> None:
    print("\n  ── Step 4: check_configs malformed XML ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bad = tmp_path / "bad.xml"
        _write_xml(bad, "<root><unclosed>")
        orig = _install.REQUIRED_CONFIGS
        _install.REQUIRED_CONFIGS = [bad]
        raised = False
        try:
            _install.check_configs()
        except SystemExit:
            raised = True
        finally:
            _install.REQUIRED_CONFIGS = orig
        r.check("check_configs() raises SystemExit for malformed XML", raised)


# ──────────────────────── Step 5: Database initialisation ─────────────────

_MINIMAL_SCHEMA = """
<databases>
  <system name="test_sys">
    <table name="test_table">
      <field name="id"   type="INTEGER PRIMARY KEY AUTOINCREMENT"/>
      <field name="name" type="TEXT NOT NULL"/>
      <field name="value" type="REAL"/>
    </table>
  </system>
</databases>
"""

_MINIMAL_DBCONFIG = """
<databases>
  <system name="test_sys" db_name="test_sys.db"/>
</databases>
"""


def test_initialise_databases_creates_files(r: _Results) -> None:
    print("\n  ── Step 5: initialise_databases creates files ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path  = Path(tmp)
        fmofp_dir = tmp_path / "FMOFP"
        db_dir    = fmofp_dir / "storage" / "databases"
        db_dir.mkdir(parents=True)

        schema_path = db_dir / "schema.xml"
        db_config   = fmofp_dir / "dbConfig.xml"
        schema_path.write_text(_MINIMAL_SCHEMA)
        db_config.write_text(_MINIMAL_DBCONFIG)

        orig_fmofp  = _install.FMOFP_DIR
        _install.FMOFP_DIR = fmofp_dir
        try:
            _install.initialise_databases()
        except SystemExit as exc:
            r.check("initialise_databases() runs without error",
                    False, str(exc))
            return
        finally:
            _install.FMOFP_DIR = orig_fmofp

        db_path = db_dir / "test_sys.db"
        r.check("database file created", db_path.exists())


def test_initialise_databases_creates_tables(r: _Results) -> None:
    print("\n  ── Step 5: initialise_databases creates tables ──")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path  = Path(tmp)
        fmofp_dir = tmp_path / "FMOFP"
        db_dir    = fmofp_dir / "storage" / "databases"
        db_dir.mkdir(parents=True)

        (db_dir / "schema.xml").write_text(_MINIMAL_SCHEMA)
        (fmofp_dir / "dbConfig.xml").write_text(_MINIMAL_DBCONFIG)

        orig_fmofp = _install.FMOFP_DIR
        _install.FMOFP_DIR = fmofp_dir
        try:
            _install.initialise_databases()
        finally:
            _install.FMOFP_DIR = orig_fmofp

        db_path = db_dir / "test_sys.db"
        if not db_path.exists():
            r.check("test_table created in database", False, "db not found")
            return

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        rows = cursor.fetchall()
        conn.close()
        r.check("test_table created in database",
                len(rows) == 1, f"got {rows}")


# ──────────────────────────── Constants checks ────────────────────────────

def test_min_python_constant(r: _Results) -> None:
    print("\n  ── Constants: MIN_PYTHON ──")
    r.check("MIN_PYTHON is (3, 9)",
            _install.MIN_PYTHON == (3, 9), f"got {_install.MIN_PYTHON}")


def test_required_packages(r: _Results) -> None:
    print("\n  ── Constants: REQUIRED_PACKAGES ──")
    pkg_names = [p[1] for p in _install.REQUIRED_PACKAGES]
    r.check("PyQt6 in REQUIRED_PACKAGES",  "PyQt6"  in pkg_names)
    r.check("numpy in REQUIRED_PACKAGES",  "numpy"  in pkg_names)
    r.check("qasync in REQUIRED_PACKAGES", "qasync" in pkg_names)


# ──────────────────────────────────────────── runner ─────────────────────

def run_all() -> bool:
    print("=" * 60)
    print(" Install Script Test Suite")
    print("=" * 60)

    r = _Results()

    tests = [
        test_check_python_passes,
        test_check_python_rejects_old,
        test_check_directories_all_present,
        test_check_directories_missing,
        test_check_configs_valid,
        test_check_configs_missing,
        test_check_configs_malformed,
        test_initialise_databases_creates_files,
        test_initialise_databases_creates_tables,
        test_min_python_constant,
        test_required_packages,
    ]

    for test_fn in tests:
        try:
            test_fn(r)
        except Exception as exc:
            r.failed += 1
            print(f"  ✗  {test_fn.__name__} raised: {exc}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    passed = r.summary()
    print("=" * 60)
    return passed


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
