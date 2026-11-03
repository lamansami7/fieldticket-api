"""Verify RapidAPI gateway identity before trusting subscriber headers.

This module does not enable RapidAPI authentication by itself. Integrate it
with persistent subscriber records and quota enforcement before deployment.
"""
import os
import secrets
from fastapi import HTTPException


def verified_rapidapi_subscriber(proxy_secret: str | None, username: str | None) -> str:
    """Return a verified subscriber name or reject the request.

    Never trust X-RapidAPI-User without a matching gateway proxy secret.
    The expected secret must be configured only in the server environment.
    """
    expected = os.environ.get("RAPIDAPI_PROXY_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="RapidAPI authentication not configured")
    if not proxy_secret or not secrets.compare_digest(proxy_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid RapidAPI gateway credentials")
    if not username or not username.strip() or len(username) > 200:
        raise HTTPException(status_code=401, detail="Missing RapidAPI subscriber identity")
    return username.strip()
