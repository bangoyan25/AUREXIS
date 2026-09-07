"""Regression tests for production dependency declarations.

Ensures dependencies required at runtime (like email-validator for Pydantic EmailStr)
are declared in [project.dependencies] rather than dev-only extras.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.api.v1.auth import LoginRequest, RegisterRequest


def test_email_validator_declared_in_production_dependencies() -> None:
    """Regression test: email-validator must be in project.dependencies.

    Railway Dockerfile installs `pip install .` without `--extra dev`.
    If email-validator is only in dev dependencies, the production container
    crashes on import: `ModuleNotFoundError: No module named 'email_validator'`.
    """
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    production_deps = data.get("project", {}).get("dependencies", [])
    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])

    has_email_validator_in_prod = any(
        dep.startswith("email-validator") or "pydantic[email]" in dep
        for dep in production_deps
    )

    assert has_email_validator_in_prod, (
        "email-validator must be in [project.dependencies] for production Docker builds!"
    )

    # Must NOT be duplicated in dev dependencies
    has_email_validator_in_dev = any(
        dep.startswith("email-validator") for dep in dev_deps
    )
    assert not has_email_validator_in_dev, (
        "email-validator should only be in production dependencies, not duplicated in dev"
    )


def test_auth_requests_validate_email_successfully() -> None:
    """Verify RegisterRequest and LoginRequest correctly parse email with email-validator."""
    reg = RegisterRequest(
        email="trader@aurexis.io",  # type: ignore[arg-type]
        password="ValidPassword123!",
        display_name="Trader One",
    )
    assert reg.email == "trader@aurexis.io"

    login = LoginRequest(
        email="trader@aurexis.io",  # type: ignore[arg-type]
        password="ValidPassword123!",
    )
    assert login.email == "trader@aurexis.io"

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="invalid-email-no-domain",  # type: ignore[arg-type]
            password="ValidPassword123!",
            display_name="Trader One",
        )
