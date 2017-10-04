from enum import Enum


class _Access(Enum):
    Allow = "Allow"
    Deny = "Deny"


ALLOW = _Access.Allow
DENY = _Access.Deny


class AuthException(Exception):
    pass
