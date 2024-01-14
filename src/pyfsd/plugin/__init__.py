# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""PyFSD plugin architecture."""
from typing import Optional

__all__ = ["API_LEVEL", "PreventEvent"]

API_LEVEL = 3


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event.

    Attributes:
        result: The event result reported by plugin.
    """

    result: dict

    def __init__(self, result: Optional[dict] = None) -> None:
        if result is None:
            result = {}
        self.result = result
