# app/core/limiter.py
"""Shared slowapi Limiter instance.

Endpoints import `limiter` and apply `@limiter.limit("...")` decorators.
Tests can disable limiting via `app.state.limiter.enabled = False`.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter"]
