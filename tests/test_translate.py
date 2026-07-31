"""Behavioural tests for the translate extension.

These cover what the packaging checks cannot: that a gcode file actually comes
out the far side with the coordinates moved where they should be.

Note the shape of the fixtures: translation only begins once a line matches the
layer-start regex, and stops again at the stop regex. Everything outside that
window -- start gcode, end gcode -- is copied through untouched, which is why
almost every fixture here opens with a ;LAYER:0 marker.
"""

import os

import pytest

from conftest import LAYER_START_REGEX, STOP_REGEX, VERSION

LAYER = ";LAYER:0"
END = "; Filament-specific end gcode"


def coords(lines, prefix="G1"):
    """Pull the X/Y/... arguments off every line whose command is `prefix`."""
    found = []
    for line in lines:
        tokens = line.split(";")[0].split()
        if not tokens or tokens[0] != prefix:
            continue
        args = {}
        for token in tokens[1:]:
            if token[:1].isalpha() and len(token) > 1:
                args[token[0].upper()] = token[1:]
        found.append(args)
    return found


class TestTranslationWindow:
    """Only gcode between the layer-start and stop markers gets moved."""

    def test_preamble_is_not_shifted(self, run):
        # Start gcode -- priming line, bed levelling -- must stay put, or the
        # printer would prime off the bed.
        _, lines = run(
            ["G90", "G1 X0 Y0 E10", LAYER, "G1 X0 Y0"],
            [(50.0, 50.0)],
        )
        assert coords(lines) == [
            {"X": "0", "Y": "0", "E": "10"},
            {"X": "50", "Y": "50"},
        ]

    def test_end_gcode_is_not_shifted(self, run):
        _, lines = run(
            ["G90", LAYER, "G1 X1 Y1", END, "G1 X0 Y0"],
            [(50.0, 50.0)],
        )
        assert coords(lines) == [
            {"X": "51", "Y": "51"},
            {"X": "0", "Y": "0"},
        ]


class TestSingleShift:
    def test_absolute_moves_are_shifted(self, run):
        _, lines = run(
            ["G90", LAYER, "G1 X10 Y20 E5", "G1 X0 Y0"],
            [(5.0, 2.5)],
        )
        assert coords(lines) == [
            {"X": "15", "Y": "22.5", "E": "5"},
            {"X": "5", "Y": "2.5"},
        ]

    def test_negative_shift(self, run):
        _, lines = run(["G90", LAYER, "G1 X10 Y10"], [(-2.5, -10.0)])
        assert coords(lines) == [{"X": "7.5", "Y": "0"}]

    def test_relative_moves_are_left_alone(self, run):
        # After G91 the coordinates are deltas, so shifting them would move the
        # model again on every single move.
        _, lines = run(
            ["G90", LAYER, "G91", "G1 X10 Y20", "G90", "G1 X10 Y20"],
            [(5.0, 5.0)],
        )
        assert coords(lines) == [
            {"X": "10", "Y": "20"},
            {"X": "15", "Y": "25"},
        ]

    def test_z_and_extrusion_are_untouched(self, run):
        _, lines = run(["G90", LAYER, "G1 X1 Y1 Z0.3 E12.5 F1800"], [(1.0, 1.0)])
        assert coords(lines) == [
            {"X": "2", "Y": "2", "Z": "0.3", "E": "12.5", "F": "1800"}
        ]

    def test_g0_travel_moves_are_shifted(self, run):
        _, lines = run(["G90", LAYER, "G0 X10 Y10"], [(5.0, 5.0)])
        assert coords(lines, prefix="G0") == [{"X": "15", "Y": "15"}]

    def test_non_motion_commands_pass_through(self, run):
        _, lines = run(
            ["G90", LAYER, "M104 S200", "T0", "G1 X1 Y1"],
            [(1.0, 1.0)],
        )
        assert "M104 S200" in lines
        assert "T0" in lines

    def test_g4_dwell_is_not_treated_as_a_move(self, run):
        # Only G0-G3 are moves; G4 P100 must not have its arguments rewritten.
        _, lines = run(["G90", LAYER, "G4 P100"], [(5.0, 5.0)])
        assert "G4 P100" in lines

    def test_fractional_shift_is_rounded_to_three_places(self, run):
        _, lines = run(["G90", LAYER, "G1 X1.0005 Y2"], [(0.001, 0.0)])
        x = coords(lines)[0]["X"]
        assert len(x.split(".")[1]) <= 3

    def test_header_records_the_version(self, run):
        _, lines = run(["G90", LAYER, "G1 X1 Y1"], [(0.0, 0.0)])
        assert lines[0] == "; Processed by OctoPrint-TranslateModel " + VERSION

    def test_output_path_is_derived_from_the_input(self, run):
        out_path, _ = run(["G90", LAYER, "G1 X1 Y1"], [(0.0, 0.0)], name="cube.gcode")
        assert os.path.basename(out_path) == "cube.translate_1_shifts.gcode"
        assert os.path.exists(out_path)


class TestMultipleShifts:
    def test_layer_is_emitted_once_per_shift(self, run):
        _, lines = run(
            ["G90", LAYER, "G1 X10 Y10", ";LAYER:1", "G1 X20 Y20"],
            [(0.0, 0.0), (100.0, 0.0)],
        )
        # Each layer's moves come out once per shift, layer by layer, so the
        # copies print together rather than one whole model at a time.
        assert coords(lines) == [
            {"X": "10", "Y": "10"},
            {"X": "110", "Y": "10"},
            {"X": "20", "Y": "20"},
            {"X": "120", "Y": "20"},
        ]

    def test_layer_markers_are_inserted(self, run):
        _, lines = run(
            ["G90", LAYER, "G1 X1 Y1"],
            [(0.0, 0.0), (10.0, 10.0)],
        )
        assert ";TRANSLATE-MODEL_LAYER_START" in lines

    def test_stop_regex_ends_translation(self, run):
        _, lines = run(
            ["G90", LAYER, "G1 X1 Y1", END, "G1 X9 Y9"],
            [(0.0, 0.0), (10.0, 10.0)],
        )
        assert ";TRANSLATE-MODEL_STOP" in lines
        # The move after the stop marker is emitted once, not once per shift.
        assert coords(lines).count({"X": "9", "Y": "9"}) == 1

    def test_shift_count_is_in_the_output_name(self, run):
        out_path, _ = run(
            ["G90", LAYER, "G1 X1 Y1"],
            [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
            name="part.gcode",
        )
        assert os.path.basename(out_path) == "part.translate_3_shifts.gcode"


class TestLineEndings:
    def test_crlf_input_produces_crlf_output(self, translate, gcode):
        in_path = gcode("G90\r\n" + LAYER + "\r\nG1 X10 Y10\r\n", "crlf.gcode")
        out_path = translate.translate(
            [(5.0, 5.0)], in_path, (LAYER_START_REGEX, STOP_REGEX), VERSION
        )
        with open(out_path, "rb") as handle:
            body = handle.read()
        assert b"G1 X15 Y15\r\n" in body

    def test_lf_input_stays_lf(self, translate, gcode):
        in_path = gcode("G90\n" + LAYER + "\nG1 X10 Y10\n", "lf.gcode")
        out_path = translate.translate(
            [(5.0, 5.0)], in_path, (LAYER_START_REGEX, STOP_REGEX), VERSION
        )
        with open(out_path, "rb") as handle:
            body = handle.read()
        assert b"\r\n" not in body
        assert b"G1 X15 Y15\n" in body


class TestPreview:
    def test_preview_returns_gcode_instead_of_a_path(self, translate, gcode):
        in_path = gcode(["G90", LAYER, "G1 X10 Y10"], "preview.gcode")
        result = translate.translate(
            [(5.0, 5.0)], in_path, (LAYER_START_REGEX, STOP_REGEX), VERSION, True
        )
        assert not os.path.exists(result)
        assert "G1 X15 Y15" in result


class TestArguments:
    def test_rejects_a_bad_signature(self, translate):
        with pytest.raises(TypeError):
            translate.translate([(0.0, 0.0)], "nope.gcode")
