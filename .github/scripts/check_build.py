"""Structural and import checks for a built OctoPrint-TranslateModel wheel.

Usage, after `pip install --no-deps <wheel>`:

    python .github/scripts/check_build.py dist/OctoPrint_TranslateModel-*.whl

Every assertion here corresponds to something that has actually gone wrong in
this repo's packaging: the C extension going missing or being renamed, the C++
source leaking into the wheel, the octoprint.plugin entry point disappearing
when the build config was rewritten, and LICENSE dropping out of the metadata.

Kept syntax-compatible with Python 3.7, since that is the oldest interpreter
OctoPrint (and therefore this plugin) still supports.
"""

import configparser
import importlib.util
import os
import sys
import zipfile

PACKAGE = "octoprint_translatemodel"
EXT_MODULE = "_translate"
ENTRY_POINT_GROUP = "octoprint.plugin"
ENTRY_POINT_NAME = "translatemodel"

failures = []


def check(condition, message):
    if condition:
        print("  ok   {}".format(message))
    else:
        print("  FAIL {}".format(message))
        failures.append(message)


def dist_info_dir(names):
    for name in names:
        head = name.split("/")[0]
        if head.endswith(".dist-info"):
            return head
    return None


def check_wheel(path):
    print("wheel: {}".format(os.path.basename(path)))
    with zipfile.ZipFile(path) as wheel:
        names = wheel.namelist()

        # The compiled extension has to land inside the package. It was a
        # top-level `translate` module until 0.3.2 nested it to avoid colliding
        # with the unrelated `translate` package on PyPI.
        ext_suffixes = (".so", ".pyd")
        exts = [
            n
            for n in names
            if n.startswith(PACKAGE + "/") and n.endswith(ext_suffixes)
        ]
        check(
            len(exts) == 1,
            "exactly one compiled extension in {}/ (found {})".format(
                PACKAGE, exts or "none"
            ),
        )
        if exts:
            check(
                os.path.basename(exts[0]).startswith(EXT_MODULE + "."),
                "extension is named {} (found {})".format(
                    EXT_MODULE, os.path.basename(exts[0])
                ),
            )

        check(
            not [n for n in names if n.endswith((".cpp", ".c", ".h"))],
            "no C/C++ sources shipped in the wheel",
        )

        for expected in (
            PACKAGE + "/__init__.py",
            PACKAGE + "/static/js/translatemodel.js",
            PACKAGE + "/templates/translatemodel_settings.jinja2",
        ):
            check(expected in names, "{} is packaged".format(expected))

        info = dist_info_dir(names)
        check(info is not None, "wheel contains a .dist-info directory")
        if info is None:
            return

        # setuptools >=77 writes license files to .dist-info/licenses/, older
        # versions put them directly in .dist-info/ -- accept either.
        check(
            any(
                n.startswith(info + "/")
                and os.path.basename(n) == "LICENSE"
                for n in names
            ),
            "LICENSE recorded in {}".format(info),
        )

        ep_path = info + "/entry_points.txt"
        check(ep_path in names, "entry_points.txt recorded")
        if ep_path in names:
            parser = configparser.ConfigParser()
            parser.read_string(wheel.read(ep_path).decode("utf-8"))
            declared = (
                parser[ENTRY_POINT_GROUP].get(ENTRY_POINT_NAME)
                if parser.has_section(ENTRY_POINT_GROUP)
                else None
            )
            check(
                declared == PACKAGE,
                "{} entry point {} -> {} (found {})".format(
                    ENTRY_POINT_GROUP, ENTRY_POINT_NAME, PACKAGE, declared
                ),
            )

        metadata = wheel.read(info + "/METADATA").decode("utf-8")
        headers = {}
        for line in metadata.splitlines():
            if not line.strip():
                break
            if ": " in line:
                key, _, value = line.partition(": ")
                headers.setdefault(key.lower(), value)
        check(
            headers.get("requires-python", "") != "",
            "Requires-Python is declared (found {!r})".format(
                headers.get("requires-python", "")
            ),
        )
        # License-Expression is the PEP 639 spelling used by setuptools >=77.
        check(
            bool(headers.get("license") or headers.get("license-expression")),
            "license is declared in METADATA",
        )


def check_import():
    print("installed extension:")

    # Drop the working directory so an in-tree ./octoprint_translatemodel can
    # never be mistaken for the installed package (which is the only one with a
    # compiled extension in it).
    cwd = os.getcwd()
    sys.path[:] = [p for p in sys.path if p not in ("", ".", cwd)]

    spec = importlib.util.find_spec(PACKAGE)
    if spec is None or not spec.submodule_search_locations:
        check(False, "installed {} package is importable".format(PACKAGE))
        return
    location = list(spec.submodule_search_locations)[0]
    check(True, "installed at {}".format(location))

    candidates = [
        os.path.join(location, n)
        for n in sorted(os.listdir(location))
        if n.startswith(EXT_MODULE + ".") and n.endswith((".so", ".pyd"))
    ]
    check(len(candidates) == 1, "one installed {} extension".format(EXT_MODULE))
    if not candidates:
        return

    # Loaded by file rather than `import octoprint_translatemodel._translate`,
    # because importing the parent package pulls in OctoPrint and these jobs
    # deliberately install with --no-deps.
    name = "{}.{}".format(PACKAGE, EXT_MODULE)
    ext_spec = importlib.util.spec_from_file_location(name, candidates[0])
    module = importlib.util.module_from_spec(ext_spec)
    ext_spec.loader.exec_module(module)
    check(callable(getattr(module, "translate", None)), "translate() is callable")


def main(argv):
    if len(argv) != 1:
        print("usage: check_build.py <wheel>", file=sys.stderr)
        return 2

    check_wheel(argv[0])
    check_import()

    if failures:
        print("\n{} check(s) failed".format(len(failures)), file=sys.stderr)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
