import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from sqlalchemy_auth import AuthSession, AuthQuery, ALLOW, instrument_scoped_session, AuthException
from sqlalchemy_auth.auth_session import _BadgeContext


class TestUserContext:
    def test_context(self):
        session = AuthSession()
        assert session.badge is ALLOW
        with _BadgeContext(session):
            session.badge = "tmp1"
            with _BadgeContext(session):
                assert session.badge == "tmp1"
                session.badge = "tmp2"
            assert session.badge == "tmp1"
        assert session.badge is ALLOW

    def test_session(self):
        session = AuthSession("badge1")
        assert session.badge == "badge1"
        session.badge = "badge2"
        assert session.badge == "badge2"
        with session.switch_badge("tmp"):
            assert session.badge == "tmp"
        assert session.badge == "badge2"


class TestScopedSessionSU:
    def test_scoped_session(self):
        session = scoped_session(sessionmaker(class_=AuthSession,
                                              query_cls=AuthQuery))
        session().switch_badge(None)
        with pytest.raises(AttributeError):
            session.switch_badge(None)

        session().badge = 1
        session.badge = 2  # silently applied to the wrong object :/
        assert session().badge == 1

    def test_instrument_scoped_session(self):
        session = scoped_session(sessionmaker(class_=AuthSession,
                                              query_cls=AuthQuery))
        instrument_scoped_session(scoped_session)
        session.switch_badge(None)
        assert session.badge == None

class TestBakedQueries:
    def test_override_raises(self):
        with pytest.raises(AuthException):
            AuthSession(enable_baked_queries=True)

    def test_double_disable(self):
        # AuthSession disables enable_baked_queries, make it not matter if the
        #  user also sets it to False.
        session = AuthSession(enable_baked_queries=False)

    def test_default_false(self):
        session = AuthSession()
        assert session.enable_baked_queries == False
