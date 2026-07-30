"""Assert that OctoPrint can discover and load the installed plugin.

Usage, after `pip install <wheel>` (with dependencies, so OctoPrint is present):

    python .github/scripts/check_plugin_load.py

This follows the same path OctoPrint's plugin manager takes at startup --
resolve the octoprint.plugin entry point, import the module behind it, call
__plugin_load__(), and inspect what comes out -- without booting a server. It
catches the failures check_build.py cannot see: a wheel whose entry point
resolves to nothing importable, an extension that will not load through the
normal `from . import _translate` path, and a plugin class that no longer
registers as the mixins OctoPrint dispatches on.
"""

import importlib.metadata as md
import os
import sys
import tomllib

DIST = "OctoPrint-TranslateModel"
PACKAGE = "octoprint_translatemodel"
ENTRY_POINT_GROUP = "octoprint.plugin"
ENTRY_POINT_NAME = "translatemodel"
HOOK = "octoprint.plugin.softwareupdate.check_config"

failures = []


def check(condition, message):
    if condition:
        print("  ok   {}".format(message))
    else:
        print("  FAIL {}".format(message))
        failures.append(message)


def find_entry_point():
    points = md.entry_points()
    # entry_points() grew a select()/group= API in 3.10; older versions return a
    # dict keyed by group.
    if hasattr(points, "select"):
        group = list(points.select(group=ENTRY_POINT_GROUP))
    else:
        group = list(points.get(ENTRY_POINT_GROUP, []))
    for point in group:
        if point.name == ENTRY_POINT_NAME:
            return point
    return None


def main():
    # Keep an in-tree ./octoprint_translatemodel from shadowing the installed
    # one, which is the only copy with a compiled extension beside it.
    cwd = os.getcwd()
    sys.path[:] = [p for p in sys.path if p not in ("", ".", cwd)]

    print("installed distribution:")
    try:
        installed = md.version(DIST)
    except md.PackageNotFoundError:
        installed = None
    check(installed is not None, "{} is installed (found {})".format(DIST, installed))
    if installed is None:
        return 1

    with open(os.path.join(cwd, "pyproject.toml"), "rb") as handle:
        declared = tomllib.load(handle)["project"]["version"]
    check(
        installed == declared,
        "installed version matches pyproject ({} vs {})".format(installed, declared),
    )

    print("entry point:")
    point = find_entry_point()
    check(point is not None, "{} declares {}".format(ENTRY_POINT_GROUP, ENTRY_POINT_NAME))
    if point is None:
        return 1
    check(
        point.value == PACKAGE,
        "{} points at {} (found {})".format(ENTRY_POINT_NAME, PACKAGE, point.value),
    )

    try:
        plugin = point.load()
    except Exception as error:
        # Most likely the compiled extension is missing or unloadable, since
        # __init__.py imports it at module scope.
        check(False, "entry point imports {} ({}: {})".format(PACKAGE, type(error).__name__, error))
        return 1
    check(getattr(plugin, "__name__", None) == PACKAGE, "entry point imports {}".format(PACKAGE))
    check(bool(getattr(plugin, "__plugin_name__", "")), "__plugin_name__ is set")
    check(
        bool(getattr(plugin, "__plugin_pythoncompat__", "")),
        "__plugin_pythoncompat__ is set",
    )

    print("compiled extension, via the plugin's own import:")
    extension = getattr(plugin, "translate", None)
    check(extension is not None, "module exposes the extension")
    if extension is not None:
        for name in ("translate", "test"):
            check(
                callable(getattr(extension, name, None)),
                "extension provides {}()".format(name),
            )

    print("plugin load:")
    plugin.__plugin_load__()
    implementation = getattr(plugin, "__plugin_implementation__", None)
    check(implementation is not None, "__plugin_load__() set an implementation")
    if implementation is None:
        return 1

    import octoprint.plugin

    for mixin in (
        "SettingsPlugin",
        "AssetPlugin",
        "TemplatePlugin",
        "SimpleApiPlugin",
        "StartupPlugin",
        "EventHandlerPlugin",
    ):
        check(
            isinstance(implementation, getattr(octoprint.plugin, mixin)),
            "implementation registers as {}".format(mixin),
        )

    hooks = getattr(plugin, "__plugin_hooks__", {})
    check(callable(hooks.get(HOOK)), "{} hook is registered".format(HOOK))

    if failures:
        print("\n{} check(s) failed".format(len(failures)), file=sys.stderr)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
