"""Shared pipeline stage and error types for experience card pipeline and embedding."""

from enum import Enum
from typing import Optional


class PipelineStage(str, Enum):
    """Pipeline stage identifiers for error reporting."""
    REWRITE = "rewrite"
    EXTRACT = "extract"
    VALIDATE = "validate"
    PERSIST = "persist"
    EMBED = "embed"


class PipelineError(Exception):
    """Pipeline error with stage context."""
    def __init__(self, stage: PipelineStage, message: str, cause: Optional[Exception] = None):
        self.stage = stage
        self.message = message
        self.cause = cause
        super().__init__(f"[{stage.value}] {message}")
