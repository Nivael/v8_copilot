"""Compatibility import for frozen eval runners; routing lives in production."""
from deterministic_router import RoutePrediction, route_question

__all__ = ["RoutePrediction", "route_question"]
