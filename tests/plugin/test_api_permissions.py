"""Permission gating on the plugin's API commands.

on_api_command is the plugin's only externally reachable entry point, and
every branch of it is guarded by an OctoPrint permission. Rather than stand up
a flask request context to make those checks evaluate, the Permissions object
the module imported is swapped for a stub -- the plugin reads it by module
attribute, so this exercises the real branching.

TranslateWorker is stubbed too, so nothing actually spawns a thread or touches
the disk; the tests assert on what the plugin decided to hand it.
"""

import pytest

pytest.importorskip("octoprint")

import octoprint.filemanager  # noqa: E402
import octoprint_translatemodel  # noqa: E402


def fake_valid_file_type(name, type=None):
    """Stand-in for octoprint.filemanager.valid_file_type.

    The real one asks the plugin manager which extensions are registered, which
    needs a booted OctoPrint. Which extensions count as gcode is OctoPrint's
    business anyway; what matters here is the plugin's branching on the answer.
    """
    return name.endswith((".gcode", ".gco", ".g"))


class FakePermission:
    def __init__(self, allowed):
        self.allowed = allowed

    def can(self):
        return self.allowed


class FakePermissions:
    def __init__(self, upload=True, select=True, print_=True):
        self.FILES_UPLOAD = FakePermission(upload)
        self.FILES_SELECT = FakePermission(select)
        self.PRINT = FakePermission(print_)


class RecordingWorker:
    started = []

    def __init__(self, plugin, shifts, file, after_translate, regexTuple, index):
        self.args = dict(
            shifts=shifts,
            file=file,
            after_translate=after_translate,
            regexTuple=regexTuple,
            index=index,
        )

    def start(self):
        RecordingWorker.started.append(self.args)


class FakeSettings:
    def get(self, keys):
        return {"layerStartRegex": "^;LAYER", "stopRegex": "(end)"}[keys[0]]


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


class FakePluginManager:
    def __init__(self):
        self.messages = []

    def send_plugin_message(self, identifier, payload):
        self.messages.append(payload)


@pytest.fixture
def api(monkeypatch):
    """A plugin instance with permissions and the worker stubbed out."""
    RecordingWorker.started = []
    monkeypatch.setattr(octoprint_translatemodel, "TranslateWorker", RecordingWorker)
    monkeypatch.setattr(
        octoprint.filemanager, "valid_file_type", fake_valid_file_type
    )

    plugin = octoprint_translatemodel.TranslatemodelPlugin()
    plugin.translating = []
    plugin.delete_files = []
    plugin._logger = FakeLogger()
    plugin._settings = FakeSettings()
    plugin._plugin_manager = FakePluginManager()

    def configure(**kwargs):
        monkeypatch.setattr(
            octoprint_translatemodel, "Permissions", FakePermissions(**kwargs)
        )
        return plugin

    plugin.configure = configure
    return plugin


def translate_request(at="nothing", file="cube.gcode", shifts=((10, 20),)):
    return {"file": file, "shifts": [list(s) for s in shifts], "at": at}


class TestUploadPermission:
    def test_translate_needs_files_upload(self, api):
        plugin = api.configure(upload=False)
        plugin.on_api_command("translate", translate_request())
        assert RecordingWorker.started == []

    def test_preview_needs_files_upload(self, api):
        plugin = api.configure(upload=False)
        plugin.on_api_command("preview", translate_request())
        assert RecordingWorker.started == []

    def test_translate_runs_with_files_upload(self, api):
        plugin = api.configure(upload=True)
        plugin.on_api_command("translate", translate_request())
        assert len(RecordingWorker.started) == 1


class TestAfterTranslateIsDowngraded:
    def test_load_requires_files_select(self, api):
        plugin = api.configure(select=False)
        plugin.on_api_command("translate", translate_request(at="load"))
        assert RecordingWorker.started[0]["after_translate"] == ""

    def test_load_is_allowed_with_files_select(self, api):
        plugin = api.configure(select=True)
        plugin.on_api_command("translate", translate_request(at="load"))
        assert RecordingWorker.started[0]["after_translate"] == "load"

    def test_print_without_print_permission_falls_back_to_load(self, api):
        plugin = api.configure(select=True, print_=False)
        plugin.on_api_command("translate", translate_request(at="print"))
        assert RecordingWorker.started[0]["after_translate"] == "load"

    def test_print_without_files_select_does_nothing_after(self, api):
        plugin = api.configure(select=False, print_=True)
        plugin.on_api_command("translate", translate_request(at="print"))
        assert RecordingWorker.started[0]["after_translate"] == "nothing"

    def test_print_is_allowed_with_both(self, api):
        plugin = api.configure(select=True, print_=True)
        plugin.on_api_command("translate", translate_request(at="print"))
        assert RecordingWorker.started[0]["after_translate"] == "print"

    def test_print_and_delete_needs_both_too(self, api):
        plugin = api.configure(select=True, print_=False)
        plugin.on_api_command("translate", translate_request(at="printAndDelete"))
        assert RecordingWorker.started[0]["after_translate"] == "load"


class TestRequestHandling:
    def test_shifts_are_coerced_to_float_pairs(self, api):
        plugin = api.configure()
        plugin.on_api_command("translate", translate_request(shifts=(("10", "20.5"),)))
        assert RecordingWorker.started[0]["shifts"] == [(10.0, 20.5)]

    def test_settings_patterns_are_passed_through(self, api):
        plugin = api.configure()
        plugin.on_api_command("translate", translate_request())
        assert RecordingWorker.started[0]["regexTuple"] == ("^;LAYER", "(end)")

    def test_non_gcode_is_rejected(self, api):
        plugin = api.configure()
        plugin.on_api_command("translate", translate_request(file="notes.txt"))
        assert RecordingWorker.started == []
        assert plugin._plugin_manager.messages[-1]["state"] == "invalid"

    def test_preview_always_previews(self, api):
        plugin = api.configure()
        plugin.on_api_command("preview", translate_request(at="print"))
        assert RecordingWorker.started[0]["after_translate"] == "preview"

    def test_duplicate_request_reports_running_instead_of_starting_again(self, api):
        # The same file with the same shifts, while the first is still in
        # flight. This used to raise UnboundLocalError, so the UI got a 500
        # rather than the "already running" notification.
        plugin = api.configure()
        plugin.on_api_command("translate", translate_request())
        plugin.on_api_command("translate", translate_request())

        assert len(RecordingWorker.started) == 1
        assert plugin._plugin_manager.messages[-1]["state"] == "running"
        assert plugin._plugin_manager.messages[-1]["shifts"] == 1

    def test_different_shifts_are_not_a_duplicate(self, api):
        plugin = api.configure()
        plugin.on_api_command("translate", translate_request(shifts=((10, 20),)))
        plugin.on_api_command("translate", translate_request(shifts=((30, 40),)))

        assert len(RecordingWorker.started) == 2

    def test_test_command_starts_nothing(self, api):
        plugin = api.configure()
        plugin.on_api_command("test", {})
        assert RecordingWorker.started == []
