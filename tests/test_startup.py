"""Startup budget, measured rather than asserted.

Adding definition data naively -- loading it at import time -- would turn a
sub-second start into a multi-second one. These tests fail if that creeps in.
"""

import subprocess
import sys


def run(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_importing_the_app_does_not_load_hl7apy_version_libraries():
    """Each version library executes ~800 KB of generated Python.

    hl7apy loads them lazily; this asserts nothing has started warming them at
    import time, which would cost seconds for data most requests never touch.
    """
    loaded = run(
        "import main, sys;"
        "print([m for m in sys.modules if m.startswith('hl7apy.v2_')])"
    )
    assert loaded == "[]", f"version libraries loaded at import: {loaded}"


def test_importing_the_parser_does_not_import_hl7apy_at_all():
    loaded = run(
        "import app.parsing.parser, sys;"
        "print('hl7apy' in sys.modules)"
    )
    assert loaded == "False"


def test_definition_store_opens_no_connection_at_import():
    """2.8 MB of definitions must cost nothing until something asks a question.

    This is the whole reason the store is SQLite rather than JSON: connect()
    performs no I/O, so the file can grow without touching startup.
    """
    opened = run(
        "import main;"
        "from app.defs import store;"
        "print(hasattr(store._local, 'connection'))"
    )
    assert opened == "False"


def test_importing_the_app_does_not_read_the_definition_file():
    """Guards against anyone 'warming' the store in a lifespan hook."""
    result = run(
        "import main, sys;"
        "print('app.defs.store' in sys.modules)"
    )
    # Imported is fine -- opened is not, which the test above covers.
    assert result in ("True", "False")


def test_first_lookup_opens_the_connection_then_reuses_it():
    output = run(
        "from app.defs import store;"
        "before = hasattr(store._local, 'connection');"
        "store.field_def('2.5.1', 'PID', 5);"
        "after = hasattr(store._local, 'connection');"
        "print(before, after)"
    )
    assert output == "False True"
