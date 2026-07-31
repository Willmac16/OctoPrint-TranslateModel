"""The extension must raise on bad input rather than take the process down.

Every case here crashed the interpreter before the argument handling was
fixed: a segfault for the malformed shift lists, and a std::terminate abort
for the invalid regex. The regex one is the reachable one -- the patterns come
straight from plugin settings, so a typo in a settings field was enough to kill
OctoPrint mid-print.
"""

import pytest

from conftest import LAYER_START_REGEX, STOP_REGEX, VERSION

GOOD_SHIFTS = [(1.0, 1.0)]


@pytest.fixture
def path(gcode):
    return gcode(["G90", ";LAYER:0", "G1 X10 Y10"])


class TestShiftValidation:
    def test_shift_with_one_coordinate(self, translate, path):
        with pytest.raises(ValueError):
            translate.translate([(1.0,)], path, (LAYER_START_REGEX, STOP_REGEX), VERSION)

    def test_empty_shift(self, translate, path):
        with pytest.raises(ValueError):
            translate.translate([()], path, (LAYER_START_REGEX, STOP_REGEX), VERSION)

    def test_no_shifts_at_all(self, translate, path):
        with pytest.raises(ValueError):
            translate.translate([], path, (LAYER_START_REGEX, STOP_REGEX), VERSION)

    def test_non_numeric_coordinates(self, translate, path):
        # Same as float("a"): ValueError for an unparseable string, TypeError
        # for something with no float conversion at all.
        with pytest.raises(ValueError):
            translate.translate(
                [("a", "b")], path, (LAYER_START_REGEX, STOP_REGEX), VERSION
            )

    def test_shift_that_is_not_a_sequence(self, translate, path):
        with pytest.raises(TypeError):
            translate.translate([None], path, (LAYER_START_REGEX, STOP_REGEX), VERSION)

    def test_shifts_that_are_not_a_sequence(self, translate, path):
        with pytest.raises(TypeError):
            translate.translate(None, path, (LAYER_START_REGEX, STOP_REGEX), VERSION)

    def test_extra_coordinates_are_ignored(self, translate, path):
        # More than x and y is harmless; only the first two are read.
        out = translate.translate(
            [(1.0, 2.0, 3.0)], path, (LAYER_START_REGEX, STOP_REGEX), VERSION
        )
        assert out.endswith(".gcode")

    def test_a_long_shift_list_does_not_blow_the_stack(self, translate, path):
        # This many shifts used to be a 16MB stack-allocated VLA against an 8MB
        # stack. It is slow but it must not crash.
        out = translate.translate(
            [(0.0, 0.0)] * 1000000, path, (LAYER_START_REGEX, STOP_REGEX), VERSION
        )
        assert out.endswith(".gcode")


class TestRegexValidation:
    @pytest.mark.parametrize(
        "pattern", ["[unclosed", "(unbalanced", "a{2,1}", "*leading"]
    )
    def test_invalid_layer_start_regex_raises(self, translate, path, pattern):
        with pytest.raises(ValueError):
            translate.translate(GOOD_SHIFTS, path, (pattern, STOP_REGEX), VERSION)

    def test_invalid_stop_regex_raises(self, translate, path):
        with pytest.raises(ValueError):
            translate.translate(
                GOOD_SHIFTS, path, (LAYER_START_REGEX, "[unclosed"), VERSION
            )

    def test_the_process_survives_a_bad_regex(self, translate, path):
        # The point of the fix: a bad pattern is recoverable, so a later good
        # call still works.
        with pytest.raises(ValueError):
            translate.translate(GOOD_SHIFTS, path, ("[unclosed", STOP_REGEX), VERSION)

        out = translate.translate(
            GOOD_SHIFTS, path, (LAYER_START_REGEX, STOP_REGEX), VERSION
        )
        assert out.endswith(".gcode")
