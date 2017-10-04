from sqlalchemy.orm import Session
from sqlalchemy_auth import AuthException, ALLOW, DENY
from .utils import _Settings


class _UserContext:
    def __init__(self, session):
        self.session = session
        self.auth_user = self.session._auth_settings.user

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session._auth_settings.user = self.auth_user


class AuthSession(Session):
    """
    AuthSession manages user/_auth_settings and passes it to queries.
    """
    def __init__(self, user=ALLOW, *args, **kwargs):
        self._auth_settings = _Settings()
        self._auth_settings.user = user
        super().__init__(*args, **kwargs)

    def su(self, user=ALLOW):
        context = _UserContext(self)
        self._auth_settings.user = user
        return context

    def _save_impl(self, state):
        if self._auth_settings.user is DENY:
            raise AuthException("Access is denied")
        if self._auth_settings.user is not ALLOW:
            state.object.add_auth_insert_data(self._auth_settings.user)
        super()._save_impl(state)


def instrument_scoped_session(scoped_session):
    """
    ScopedSession is unaware of the su method; inform it.
    """
    from sqlalchemy.orm.scoping import instrument
    setattr(scoped_session, 'su', instrument('su'))
