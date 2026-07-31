"""Test fixtures for the compiled translate extension.

The extension is loaded from the *installed* package by file path rather than
with a plain import, because importing octoprint_translatemodel/__init__.py
pulls in OctoPrint, which these tests do not need and CI does not install.
"""

import importlib.util
import os
import sys

import pytest

# Drop the working directory before any test module is imported. The repo root
# holds an octoprint_translatemodel/ source directory with no compiled
# extension beside it, which would otherwise shadow the installed package that
# the tests are meant to exercise.
_CWD = os.getcwd()
sys.path[:] = [p for p in sys.path if p not in ("", ".", _CWD)]

PACKAGE = "octoprint_translatemodel"
EXT_MODULE = "_translate"

# Defaults straight out of the plugin's get_settings_defaults(), so the tests
# exercise the patterns real users actually run with.
LAYER_START_REGEX = (
    r"^;(( BEGIN_|BEFORE_)*LAYER_(CHANGE|OBJECT)|LAYER:[0-9]+|"
    r" [<]{0,1}layer [0-9]+[>,]{0,1}).*$"
)
STOP_REGEX = r"(end|disable|^; Filament-specific end gcode$)"

VERSION = "0.0.0-test"


def _load_extension():
    spec = importlib.util.find_spec(PACKAGE)
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError(
            "{} is not installed; run `pip install --no-deps dist/*.whl` first".format(
                PACKAGE
            )
        )

    location = list(spec.submodule_search_locations)[0]
    candidates = [
        os.path.join(location, name)
        for name in sorted(os.listdir(location))
        if name.startswith(EXT_MODULE + ".") and name.endswith((".so", ".pyd"))
    ]
    if not candidates:
        raise RuntimeError("no compiled {} extension in {}".format(EXT_MODULE, location))

    name = "{}.{}".format(PACKAGE, EXT_MODULE)
    ext_spec = importlib.util.spec_from_file_location(name, candidates[0])
    module = importlib.util.module_from_spec(ext_spec)
    ext_spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def translate():
    return _load_extension()


@pytest.fixture
def gcode(tmp_path):
    """Write gcode to a file and return its path.

    Takes a list of lines, or a raw string when a test cares about line
    endings.
    """

    def write(content, name="model.gcode"):
        if not isinstance(content, str):
            content = "\n".join(content) + "\n"
        path = tmp_path / name
        path.write_bytes(content.encode())
        return str(path)

    return write


@pytest.fixture
def run(translate, gcode):
    """Translate gcode and return the output lines."""

    def go(content, shifts, name="model.gcode"):
        in_path = gcode(content, name)
        out_path = translate.translate(
            shifts, in_path, (LAYER_START_REGEX, STOP_REGEX), VERSION
        )
        with open(out_path) as handle:
            return out_path, handle.read().splitlines()

    return go
