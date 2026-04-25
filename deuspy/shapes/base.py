"""Shape ABC — pure geometry, no G-code knowledge."""

from __future__ import annotations

from abc import ABC, abstractmethod

from deuspy.units import Vec3


class Shape(ABC):
    """A shape is a piece of geometry anchored in the work coordinate system.

    Strategies turn shapes into toolpaths; shapes themselves know nothing
    about cutting, feeds, or G-code.
    """

    @abstractmethod
    def bbox(self) -> tuple[Vec3, Vec3]:
        """Return (min_corner, max_corner) of the axis-aligned bounding box."""

    @property
    def anchor(self) -> Vec3:
        """The reference corner / center the shape is positioned by."""
        return self.bbox()[0]
