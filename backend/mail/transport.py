"""Compatibility facade for external mail providers."""

from mail.providers import (
    ExternalMailError,
    ExternalMailNotConfigured,
    external_send_enabled,
    external_test_mode,
    provider_name,
    public_address,
    send_external,
)

__all__ = [
    "ExternalMailError",
    "ExternalMailNotConfigured",
    "external_send_enabled",
    "external_test_mode",
    "provider_name",
    "public_address",
    "send_external",
]
