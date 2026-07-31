"""Tests for the Python half of the plugin.

Skipped unless OctoPrint is importable, so the build jobs (which install with
--no-deps) skip them and the discovery job runs them.

Scope note: on_api_command is not covered. Its first act is a permission check
through flask-principal, which needs a real request and app context to
evaluate -- standing that up is a bigger harness than this. What is covered is
everything reachable from a bare plugin instance.
"""

import pytest

pytest.importorskip("octoprint")

from conftest import LAYER_START_REGEX, STOP_REGEX, VERSION  # noqa: E402

import octoprint_translatemodel  # noqa: E402


@pytest.fixture
def plugin():
    instance = octoprint_translatemodel.TranslatemodelPlugin()
    instance._plugin_version = "9.9.9"
    # Class attributes, so they persist between instances; reset per test.
    instance.translating = []
    instance.delete_files = []
    return instance


class TestSettingsDefaults:
    def test_both_patterns_are_present(self, plugin):
        defaults = plugin.get_settings_defaults()
        assert defaults["layerStartRegex"]
        assert defaults["stopRegex"]

    def test_defaults_match_what_the_tests_exercise(self, plugin):
        # The extension tests hard-code these; if the defaults move, the tests
        # stop covering what users actually run.
        defaults = plugin.get_settings_defaults()
        assert defaults["layerStartRegex"] == LAYER_START_REGEX
        assert defaults["stopRegex"] == STOP_REGEX

    def test_defaults_are_valid_for_the_extension(self, plugin, translate, gcode):
        # The C++ side compiles these with std::regex, not Python's re. An
        # invalid default would make every translate raise.
        defaults = plugin.get_settings_defaults()
        path = gcode(["G90", ";LAYER:0", "G1 X1 Y1"])
        out = translate.translate(
            [(1.0, 1.0)],
            path,
            (defaults["layerStartRegex"], defaults["stopRegex"]),
            VERSION,
        )
        assert out.endswith(".gcode")

    def test_the_default_layer_pattern_matches_real_slicer_output(
        self, plugin, translate, gcode
    ):
        # Cura writes ;LAYER:n, PrusaSlicer writes ;LAYER_CHANGE.
        defaults = plugin.get_settings_defaults()
        for marker in (";LAYER:0", ";LAYER_CHANGE"):
            path = gcode(["G90", marker, "G1 X10 Y10"], "m.gcode")
            out = translate.translate(
                [(5.0, 5.0)],
                path,
                (defaults["layerStartRegex"], defaults["stopRegex"]),
                VERSION,
            )
            with open(out) as handle:
                body = handle.read()
            assert "X15 Y15" in body, marker


class TestUpdateInformation:
    def test_points_at_this_repository(self, plugin):
        info = plugin.get_update_information()["translatemodel"]
        assert info["user"] == "Willmac16"
        assert info["repo"] == "OctoPrint-TranslateModel"
        assert info["type"] == "github_release"

    def test_reports_the_running_version(self, plugin):
        info = plugin.get_update_information()["translatemodel"]
        assert info["current"] == "9.9.9"
        assert info["displayVersion"] == "9.9.9"

    def test_pip_url_is_templated_on_the_target_version(self, plugin):
        info = plugin.get_update_information()["translatemodel"]
        assert "{target_version}" in info["pip"]
        # The release guard checks tags against pyproject.toml precisely
        # because this URL resolves a tag to an archive.
        assert info["pip"].endswith("archive/{target_version}.zip")


class TestAssets:
    def test_declared_js_is_actually_packaged(self, plugin):
        import os

        assets = plugin.get_assets()
        package_dir = os.path.dirname(octoprint_translatemodel.__file__)
        for relative in assets["js"]:
            assert os.path.exists(os.path.join(package_dir, "static", relative))


class TestApiCommands:
    def test_commands_and_their_required_parameters(self, plugin):
        commands = plugin.get_api_commands()
        assert commands["translate"] == ["file", "shifts", "at"]
        assert commands["preview"] == ["file", "shifts"]
        assert commands["test"] == []


class FakePrinter:
    def __init__(self):
        self.unselected = False

    def unselect_file(self):
        self.unselected = True


class FakeFileManager:
    def __init__(self):
        self.removed = []

    def remove_file(self, destination, path):
        self.removed.append((destination, path))


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


@pytest.fixture
def wired(plugin):
    plugin._logger = FakeLogger()
    plugin._printer = FakePrinter()
    plugin._file_manager = FakeFileManager()
    return plugin


class TestDeleteAfterPrint:
    @pytest.mark.parametrize("event", ["PrintDone", "PrintFailed", "PrintCanceled"])
    def test_tracked_file_is_removed_when_a_print_ends(self, wired, event):
        wired.delete_files.append("copies.gcode")
        wired.on_event(event, {"origin": "local", "path": "copies.gcode"})

        assert wired._file_manager.removed == [("local", "copies.gcode")]
        assert wired._printer.unselected is True
        # Removed from tracking too, so a later event cannot delete twice.
        assert wired.delete_files == []

    def test_untracked_file_is_left_alone(self, wired):
        wired.delete_files.append("copies.gcode")
        wired.on_event("PrintDone", {"origin": "local", "path": "something-else.gcode"})

        assert wired._file_manager.removed == []
        assert wired.delete_files == ["copies.gcode"]

    def test_other_events_do_nothing(self, wired):
        wired.delete_files.append("copies.gcode")
        wired.on_event("PrintStarted", {"origin": "local", "path": "copies.gcode"})

        assert wired._file_manager.removed == []
        assert wired.delete_files == ["copies.gcode"]

    def test_non_local_origin_is_ignored(self, wired):
        # Only files this plugin wrote to local storage should be deleted.
        wired.delete_files.append("copies.gcode")
        wired.on_event("PrintDone", {"origin": "sdcard", "path": "copies.gcode"})

        assert wired._file_manager.removed == []
        assert wired.delete_files == ["copies.gcode"]
