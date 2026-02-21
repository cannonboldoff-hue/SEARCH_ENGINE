"""Search pipeline, profile views, and contact unlock."""

from .search import search_service
from .search_logic import run_search

__all__ = ["search_service", "run_search"]
