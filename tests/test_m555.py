"""Prusa M555 bed-area rewriting.

M555 tells a Prusa which part of the bed to probe for G29. Copies of a model
sit outside the original model's footprint, so the probed area has to grow to
cover all of them -- get this wrong and the printer probes the wrong region or
refuses the print.

The rewrite takes the extents of the shifts: the new origin is the original
plus the smallest shift, and the new size is the original size plus the spread
between the smallest and largest shift.
"""

import pytest

from conftest import LAYER_START_REGEX, STOP_REGEX, VERSION


def m555(lines):
    for line in lines:
        if line.startswith("M555"):
            return line
    return None


def args(line):
    out = {}
    for token in line.split(";")[0].split()[1:]:
        out[token[0].upper()] = token[1:]
    return out


class TestBedArea:
    def test_single_shift_moves_the_origin_and_keeps_the_size(self, run):
        _, lines = run(
            ["M555 X0 Y0 W100 H100", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(10.0, 20.0)],
        )
        assert args(m555(lines)) == {"X": "10", "Y": "20", "W": "100", "H": "100"}

    def test_two_shifts_grow_the_area_by_the_spread(self, run):
        # Shifts span 50 in x and 30 in y, so the probed area grows by that
        # much in each direction.
        _, lines = run(
            ["M555 X10 Y10 W100 H80", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(0.0, 0.0), (50.0, 30.0)],
        )
        assert args(m555(lines)) == {"X": "10", "Y": "10", "W": "150", "H": "110"}

    def test_negative_shifts_pull_the_origin_back(self, run):
        _, lines = run(
            ["M555 X30 Y30 W50 H50", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(-20.0, -5.0), (0.0, 0.0)],
        )
        assert args(m555(lines)) == {"X": "10", "Y": "25", "W": "70", "H": "55"}

    def test_origin_comes_from_the_smallest_shift_regardless_of_order(self, run):
        # The smallest shift is listed last here; the result must not depend on
        # the order the shifts arrive in.
        _, lines = run(
            ["M555 X0 Y0 W10 H10", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(90.0, 90.0), (5.0, 5.0)],
        )
        assert args(m555(lines)) == {"X": "5", "Y": "5", "W": "95", "H": "95"}

    def test_three_shifts_use_the_full_extent(self, run):
        _, lines = run(
            ["M555 X0 Y0 W20 H20", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(0.0, 0.0), (40.0, 10.0), (20.0, 60.0)],
        )
        assert args(m555(lines)) == {"X": "0", "Y": "0", "W": "60", "H": "80"}

    def test_rewritten_line_is_marked(self, run):
        _, lines = run(
            ["M555 X0 Y0 W100 H100", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(10.0, 10.0)],
        )
        assert ";TRANSLATE-MODEL_BED_AREA" in m555(lines)

    def test_lowercase_arguments_are_accepted(self, run):
        _, lines = run(
            ["M555 x0 y0 w100 h100", "G90", ";LAYER:0", "G1 X1 Y1"],
            [(10.0, 20.0)],
        )
        assert args(m555(lines)) == {"X": "10", "Y": "20", "W": "100", "H": "100"}

    def test_no_m555_means_no_bed_area_line(self, run):
        _, lines = run(["G90", ";LAYER:0", "G1 X1 Y1"], [(10.0, 10.0)])
        assert m555(lines) is None
