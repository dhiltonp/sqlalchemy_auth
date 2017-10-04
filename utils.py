from enum import Enum


class _Access(Enum):
    Allow = "Allow"
    Deny = "Deny"


ALLOW = _Access.Allow
DENY = _Access.Deny


class AuthException(Exception):
    pass


class _Settings:
    """
    _Settings allows an AuthSession to share the `user` with other classes
    so that if it is changed here, it changes everywhere.
    """
    def __init__(self):
        self.user = ALLOW