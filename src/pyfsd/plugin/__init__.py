# pyright: reportSelfClsParameterName=false, reportGeneralTypeIssues=false
"""PyFSD plugin architecture."""
__all__ = ["API_LEVEL", "PreventEvent"]

API_LEVEL = 3


class PreventEvent(BaseException):
    """Prevent a PyFSD plugin event.

    Attributes:
        result: The event result reported by plugin.
    """

    result: dict

    def __init__(self, result: dict = {}) -> None:
        self.result = result
