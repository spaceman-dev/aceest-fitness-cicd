"""Domain errors and the HTTP status each one maps to."""

from __future__ import annotations


class ACEestError(Exception):
    status_code = 400

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, str]:
        payload = {"error": self.__class__.__name__, "message": self.message}
        if self.field:
            payload["field"] = self.field
        return payload


class ValidationError(ACEestError):
    status_code = 400


class NotFoundError(ACEestError):
    status_code = 404
