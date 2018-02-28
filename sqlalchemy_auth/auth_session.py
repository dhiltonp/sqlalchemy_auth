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
    def __init__(self, badge=ALLOW, enable_baked_queries=False, *args, **kwargs):
        self.badge = badge
        kwargs['enable_baked_queries'] = enable_baked_queries
        super().__init__(*args, **kwargs)
        self._assert_no_baked_queries()

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

    def _assert_no_baked_queries(self):
        if self.enable_baked_queries == True:
            raise AuthException('sqlalchemy_auth is not compatible with baked queries')

def instrument_scoped_session(scoped_session):
    """
    ScopedSession is unaware of badge and switch_badge; inform it.
    """
    setattr(scoped_session, "badge", makeprop("badge"))
    setattr(scoped_session, "switch_badge", instrument("switch_badge"))
