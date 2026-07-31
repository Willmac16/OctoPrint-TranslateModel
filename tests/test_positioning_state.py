"""Absolute/relative positioning state across shift copies.

With more than one shift a layer is buffered and replayed once per copy, so
G90/G91 state has to be reset to whatever it was when the layer started before
each replay -- otherwise the second copy inherits the first copy's trailing
mode and its moves come out unshifted (or shifted when they should not be).
The implementation carries a separate flag through the replay loop for exactly
this reason; these tests hold it to that.
"""

from test_translate import coords


class TestStateAcrossCopies:
    def test_each_copy_starts_from_the_layer_entry_state(self, run):
        # The layer ends in relative mode. If the second copy inherited that,
        # its X10 would come out unshifted.
        _, lines = run(
            ["G90", ";LAYER:0", "G1 X10 Y10", "G91", ";LAYER:1", "G1 X30 Y30"],
            [(0.0, 0.0), (100.0, 0.0)],
        )
        first, second = coords(lines)[0], coords(lines)[1]
        assert first == {"X": "10", "Y": "10"}
        assert second == {"X": "110", "Y": "10"}

    def test_state_at_the_end_of_a_layer_carries_to_the_next(self, run):
        # ...and having replayed the layer, the trailing relative mode does
        # apply to what follows, so the next layer's moves are not shifted.
        _, lines = run(
            ["G90", ";LAYER:0", "G1 X10 Y10", "G91", ";LAYER:1", "G1 X30 Y30"],
            [(0.0, 0.0), (100.0, 0.0)],
        )
        assert coords(lines)[2:] == [{"X": "30", "Y": "30"}, {"X": "30", "Y": "30"}]

    def test_mode_switching_inside_a_layer(self, run):
        _, lines = run(
            [
                "G90",
                ";LAYER:0",
                "G1 X10 Y10",
                "G91",
                "G1 X5 Y5",
                "G90",
                "G1 X20 Y20",
            ],
            [(0.0, 0.0), (100.0, 0.0)],
        )
        assert coords(lines) == [
            {"X": "10", "Y": "10"},
            {"X": "5", "Y": "5"},
            {"X": "20", "Y": "20"},
            {"X": "110", "Y": "10"},
            {"X": "5", "Y": "5"},
            {"X": "120", "Y": "20"},
        ]

    def test_single_shift_tracks_mode_inline(self, run):
        # The single-shift path streams rather than buffering, but has to track
        # the same state.
        _, lines = run(
            ["G90", ";LAYER:0", "G1 X10 Y10", "G91", "G1 X5 Y5", "G90", "G1 X20 Y20"],
            [(7.0, 0.0)],
        )
        assert coords(lines) == [
            {"X": "17", "Y": "10"},
            {"X": "5", "Y": "5"},
            {"X": "27", "Y": "20"},
        ]
