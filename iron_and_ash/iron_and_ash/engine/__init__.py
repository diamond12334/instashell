"""Game engine: state, mechanics, and the main loop.

Kept intentionally light: importing this package must not pull in ``game`` (which
depends on persistence), so import ``Game`` from ``iron_and_ash.engine.game``
directly to avoid a circular import.
"""
from .state import GameState

__all__ = ["GameState"]
