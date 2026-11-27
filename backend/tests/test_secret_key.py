"""The JWT signing key must come from the environment.

Regression: auth.py fell back to SECRET_KEY = "default-secret-key", a value anyone
can read in this public repository, so tokens could be forged on any server that
forgot to set the variable.
"""
import importlib
import sys

import dotenv
import pytest


def _import_auth_fresh():
    sys.modules.pop("auth", None)
    return importlib.import_module("auth")


def test_missing_secret_key_stops_startup(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)  # ignore a local .env
    try:
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            _import_auth_fresh()
    finally:
        sys.modules.pop("auth", None)


def test_secret_key_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-test-secret-that-is-long-enough-123")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    try:
        auth = _import_auth_fresh()
        assert auth.SECRET_KEY == "a-test-secret-that-is-long-enough-123"
    finally:
        sys.modules.pop("auth", None)
