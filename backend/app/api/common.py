"""Shared RESTful response helpers.

Every JSON response follows the unified envelope ``{code, msg, data}``:
- ``code`` — mirrors the HTTP-style status semantics: 200 on success,
  401 on permission problems, 50x on server errors, etc.
- ``msg`` — human-readable message (``ok`` on success, Chinese for errors).
- ``data`` — payload; ``None`` when there is no payload.

Per project convention the HTTP status code is always 200, even for errors;
business outcomes are carried by ``code`` in the envelope.
"""
from __future__ import annotations

from typing import Any

# Business code for a successful response (mirrors HTTP 200)
OK_CODE = 200


def ok(data: Any = None, msg: str = 'ok', code: int = OK_CODE) -> dict:
    """Build a success envelope ``{code, msg, data}``."""
    return {'code': code, 'msg': msg, 'data': data}


def fail(code: int, msg: str, data: Any = None) -> dict:
    """Build an error envelope ``{code, msg, data}``.

    The HTTP status stays 200; the business failure is expressed through
    ``code`` (HTTP-style semantics, e.g. 401 / 404 / 500).
    """
    return {'code': code, 'msg': msg, 'data': data}
