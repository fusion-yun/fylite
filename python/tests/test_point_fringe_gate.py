"""The POINT fringe gate is a BAND, not a floor (F-14).

A fringe jump is an integer number of 2π in the phase, so a jumped chord can
sit above the run of its neighbours as readily as below it.  EAST #137985 c4
sat 3–166× above the same-slice median on 6 of 9 slices and reached the
reconstruction with full weight while the floor-only criterion looked the
other way.  These pins are on the pure helper; no device deck is needed.
"""
import pytest

from fylite.io.est2 import fringe_gate


def test_a_collapsed_chord_is_still_dropped():
    mags = [1.0] * 10 + [0.05]
    good = fringe_gate(mags, 0.15)
    assert good[:10] == [True] * 10 and good[10] is False


def test_a_chord_that_jumped_up_is_dropped_too():
    #: 166× (the worst slice measured on c4) and 7× (c11, 1.0–2.0 s) are out;
    #: the band's ceiling at gate 0.15 is 1/0.15 = 6.67× the median
    mags = [1.0] * 9 + [166.0, 7.0]
    good = fringe_gate(mags, 0.15)
    assert good[:9] == [True] * 9 and good[9] is False and good[10] is False


def test_the_band_is_symmetric_in_log_magnitude():
    #: a chord at gate·median and one at median/gate are the same distance
    #: from the median in log space; both sit on the edge and are dropped,
    #: just inside on either side is kept
    med, g = 1.0, 0.15
    mags = [med] * 9 + [g * med * 1.01, med / g * 0.99]
    assert fringe_gate(mags, g)[9:] == [True, True]
    mags = [med] * 9 + [g * med * 0.99, med / g * 1.01]
    assert fringe_gate(mags, g)[9:] == [False, False]


def test_a_missing_reading_is_never_good_and_the_gate_can_be_disabled():
    #: (five live chords, so the median is theirs and not the mean of two)
    mags = [1.0] * 5 + [None, 0.0, 250.0]
    assert fringe_gate(mags, 0.15) == [True] * 5 + [False, False, False]
    assert fringe_gate(mags, 0.0) == [True] * 5 + [False, False, True]


def test_the_median_is_over_the_non_zero_chords_only():
    #: dead chords must not drag the median to zero and open the band to everything
    mags = [0.0] * 6 + [1.0] * 4 + [30.0]
    good = fringe_gate(mags, 0.15)
    assert good == [False] * 6 + [True] * 4 + [False]


@pytest.mark.parametrize("gate", [0.15, 0.3])
def test_the_paired_sign_of_the_reading_does_not_matter(gate):
    assert fringe_gate([-1.0, 1.0, -1.0, 1.0, -0.01], gate) == [True, True, True, True, False]
