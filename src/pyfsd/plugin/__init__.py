# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""PyFSD plugin architecture.

Attributes:
    API_LEVEL: Current PyFSD plugin api level.
"""
from typing import Optional

__all__ = ["API_LEVEL", "PreventEvent"]

API_LEVEL = 4


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event.

    Attributes:
        result: The event result reported by plugin.
    """

    result: dict

    def __init__(self, result: Optional[dict] = None) -> None:
        """Create a PreventEvent instance."""
        if result is None:
            result = {}
        self.result = result
