"""This module tests pyfsd.define.simulation."""
from unittest import TestCase

from pyfsd.define.simulation import Int32MRand


class TestSimulation(TestCase):
    """Test if pyfsd.define.simulation works."""

    def test_Int32MRand(self) -> None:  # noqa: N802
        """Test if MRand works."""
        mrand = Int32MRand()
        mrand.srand(0)
        self.assertEqual(mrand(), 1726686868)
        self.assertEqual(mrand(), -841593560)
