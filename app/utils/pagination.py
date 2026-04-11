"""Pagination utilities."""


def sanitize_pagination(skip: int = 0, limit: int = 50, *, max_limit: int = 200) -> tuple[int, int]:
    """Clamp pagination parameters to safe bounds."""

    safe_skip = max(skip, 0)
    safe_limit = max(1, min(limit, max_limit))
    return safe_skip, safe_limit
