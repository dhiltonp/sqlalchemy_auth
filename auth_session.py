from sqlalchemy.orm import Session
from sqlalchemy_auth import AuthException, ALLOW, DENY


class _UserContext:
    """
    Allows for `with session.su():` syntax.
    """
    def __init__(self, session):
        self.session = session
        self.auth_user = self.session.auth_user

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.auth_user = self.auth_user


class AuthSession(Session):
    """
    AuthSession manages auth_user and .
    """
    def __init__(self, auth_user=ALLOW, *args, **kwargs):
        self.auth_user = auth_user
        super().__init__(*args, **kwargs)

    def su(self, auth_user=ALLOW):
        context = _UserContext(self)
        self.auth_user = auth_user
        return context

    def _save_impl(self, state):
        """
        Inject data on Session.add()
        """
        # tested in auth_query_test.py:TestAuthBaseInserts.add()
        if self.auth_user is DENY:
            raise AuthException("Access is denied")
        if self.auth_user is not ALLOW:
            state.object.add_auth_insert_data(self.auth_user)
        super()._save_impl(state)


def instrument_scoped_session(scoped_session):
    """
    ScopedSession is unaware of the su method; inform it.
    """
    from sqlalchemy.orm.scoping import instrument
    setattr(scoped_session, 'su', instrument('su'))
