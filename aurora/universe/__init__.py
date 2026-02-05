"""
AURORA Universe Module.

Provides universe construction for AURORA BMI calculations.

Universe building is SEPARATE from feature computation.
Snapshots are IMMUTABLE once written.
"""

from aurora.universe.builder import UniverseBuilder

__all__ = ["UniverseBuilder"]
