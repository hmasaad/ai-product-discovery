"""Opportunity engine: detection, mapping, ideas, and validation."""

from discovery.engine.detect import detect_candidates
from discovery.engine.pipeline import run_engine

__all__ = ["detect_candidates", "run_engine"]
