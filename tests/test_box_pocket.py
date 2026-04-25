"""Pocket(Box) toolpath tests — verify the geometry layer end-to-end."""

import pytest

from deuspy.shapes import Box
from deuspy.strategies import Pocket
from deuspy.strategies.base import MachineContext
from deuspy.units import ORIGIN


def make_ctx(*, tool=1.0, feed=100, safe_z=5.0):
    return MachineContext(
        position=ORIGIN,
        safe_z=safe_z,
        feed=feed,
        tool_diameter=tool,
    )


def test_pocket_box_basic_shape():
    box = Box(length=10, width=10, height=2, anchor=ORIGIN)
    tp = Pocket(stepdown=2.0, stepover=0.5, finish_pass=False).plan(box, make_ctx())
    # First move should be a rapid to safe Z above the start corner.
    first = tp.moves[0]
    assert first.kind == "G0"
    assert first.target.z == 5.0
    # All moves should stay within the inset bounds.
    r = 0.5  # tool_diameter/2 with tool=1.0
    for m in tp.moves[1:]:
        assert m.target.x >= 0 + r - 1e-9
        assert m.target.x <= 10 - r + 1e-9


def test_pocket_box_too_small_for_tool_raises():
    box = Box(length=2, width=2, height=1, anchor=ORIGIN)
    with pytest.raises(ValueError):
        Pocket().plan(box, make_ctx(tool=3.0))


def test_pocket_box_invalid_stepover():
    box = Box(length=10, width=10, height=2, anchor=ORIGIN)
    with pytest.raises(ValueError):
        Pocket(stepover=1.5).plan(box, make_ctx())
    with pytest.raises(ValueError):
        Pocket(stepover=0).plan(box, make_ctx())


def test_pocket_box_unsupported_shape():
    class NotABox:
        def bbox(self):
            return ORIGIN, ORIGIN

    with pytest.raises(NotImplementedError):
        Pocket().plan(NotABox(), make_ctx())  # type: ignore[arg-type]


def test_pocket_emits_finish_pass_when_requested():
    box = Box(length=10, width=10, height=2, anchor=ORIGIN)
    no_finish = Pocket(stepdown=2.0, stepover=0.5, finish_pass=False).plan(box, make_ctx())
    with_finish = Pocket(stepdown=2.0, stepover=0.5, finish_pass=True).plan(box, make_ctx())
    assert len(with_finish.moves) > len(no_finish.moves)
