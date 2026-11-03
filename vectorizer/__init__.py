"""vector-press: raster to SVG vectoriser built on a shared boundary graph (+ VTracer backend)."""
from .api import Result, vectorize
from .presets import PRESETS

__all__ = ["vectorize", "Result", "PRESETS"]
__version__ = "0.1.0"
