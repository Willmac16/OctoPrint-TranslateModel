"""Translating a file that has already been translated.

__init__.py carries a TODO about handling this better. It is reachable: the
output lands in the same folder as the input, so it shows up in OctoPrint's
file list and can be picked again. These tests pin down what currently
happens, so that "better" can be defined against a known baseline rather than
a guess.

Nothing here asserts the behaviour is desirable -- the shifts compound, which
is very likely not what a user picking the file twice expects.
"""

import os

from conftest import LAYER_START_REGEX, STOP_REGEX, VERSION
from test_translate import coords


def translate_again(translate, path, shifts):
    return translate.translate(shifts, path, (LAYER_START_REGEX, STOP_REGEX), VERSION)


class TestDoubleTranslate:
    def test_shifts_compound(self, translate, gcode):
        first_in = gcode(["G90", ";LAYER:0", "G1 X10 Y10"])
        first_out = translate_again(translate, first_in, [(5.0, 5.0)])
        second_out = translate_again(translate, first_out, [(5.0, 5.0)])

        with open(second_out) as handle:
            lines = handle.read().splitlines()

        # 10 -> 15 -> 20, rather than being recognised as already shifted.
        assert coords(lines) == [{"X": "20", "Y": "20"}]

    def test_output_name_accumulates(self, translate, gcode):
        first_in = gcode(["G90", ";LAYER:0", "G1 X1 Y1"], "cube.gcode")
        first_out = translate_again(translate, first_in, [(1.0, 1.0)])
        second_out = translate_again(translate, first_out, [(1.0, 1.0)])

        assert os.path.basename(first_out) == "cube.translate_1_shifts.gcode"
        assert (
            os.path.basename(second_out)
            == "cube.translate_1_shifts.translate_1_shifts.gcode"
        )

    def test_header_is_written_twice(self, translate, gcode):
        first_in = gcode(["G90", ";LAYER:0", "G1 X1 Y1"])
        first_out = translate_again(translate, first_in, [(1.0, 1.0)])
        second_out = translate_again(translate, first_out, [(1.0, 1.0)])

        with open(second_out) as handle:
            body = handle.read()

        header = "; Processed by OctoPrint-TranslateModel " + VERSION
        assert body.count(header) == 2

    def test_layer_markers_from_the_first_pass_are_not_layer_starts(
        self, translate, gcode
    ):
        # ;TRANSLATE-MODEL_LAYER_START does not match the layer-start pattern,
        # so a second pass does not treat the marker as a new layer. If that
        # ever changed, copies would multiply on every pass.
        first_in = gcode(["G90", ";LAYER:0", "G1 X10 Y10"])
        first_out = translate_again(translate, first_in, [(0.0, 0.0), (50.0, 0.0)])
        second_out = translate_again(translate, first_out, [(0.0, 0.0), (50.0, 0.0)])

        with open(second_out) as handle:
            lines = handle.read().splitlines()

        # Two copies from the first pass, two from the second: four, not more.
        assert len(coords(lines)) == 4
