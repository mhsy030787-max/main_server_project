from settings import MAIL_PROVIDER, RESEND_API_KEY

from .base import ExternalMailError, ExternalMailNotConfigured
from . import resend, smtp


def active_provider():
    if MAIL_PROVIDER == "resend" or (not MAIL_PROVIDER and RESEND_API_KEY):
        return resend
    if MAIL_PROVIDER == "smtp":
        return smtp
    return resend


def external_send_enabled():
    return active_provider().configured()


def external_test_mode():
    return bool(getattr(active_provider(), "test_mode", lambda: False)())


def provider_name():
    return active_provider().NAME


def public_address(user_id):
    return active_provider().public_address(user_id)


def send_external(sender, recipient, subject, body, attachment=None):
    return active_provider().send(sender, recipient, subject, body, attachment)
