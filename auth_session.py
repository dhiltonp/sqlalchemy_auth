from sqlalchemy.orm import Session
from sqlalchemy.orm.scoping import instrument, makeprop

from sqlalchemy_auth import AuthException, ALLOW, DENY


class _BadgeContext:
    """
    Allows for `with session.switch_badge():` syntax.
    """
    def __init__(self, session):
        self.session = session
        self.badge = self.session.badge

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.badge = self.badge


class AuthSession(Session):
    """
    AuthSession manages badge and .
    """
    def __init__(self, badge=ALLOW, *args, **kwargs):
        self.badge = badge
        super().__init__(*args, **kwargs)

    def switch_badge(self, badge=ALLOW):
        context = _BadgeContext(self)
        self.badge = badge
        return context

    def _save_impl(self, state):
        """
        Inject data on Session.add()
        """
        # tested in auth_query_test.py:TestAuthBaseInserts.add()
        if self.badge is DENY:
            raise AuthException("Access is denied")
        if self.badge is not ALLOW:
            state.object.add_auth_insert_data(self.badge)
        super()._save_impl(state)


def instrument_scoped_session(scoped_session):
    """
    ScopedSession is unaware of badge and switch_badge; inform it.
    """
    setattr(scoped_session, "badge", makeprop("badge"))
    setattr(scoped_session, "switch_badge", instrument("switch_badge"))
