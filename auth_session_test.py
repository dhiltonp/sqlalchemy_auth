import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from sqlalchemy_auth import AuthSession, AuthQuery, ALLOW, instrument_scoped_session
from sqlalchemy_auth.auth_session import _UserContext


class TestUserContext:
    def test_context(self):
        session = AuthSession()
        assert session.auth_user is ALLOW
        with _UserContext(session):
            session.auth_user = "tmp1"
            with _UserContext(session):
                assert session.auth_user == "tmp1"
                session.auth_user = "tmp2"
            assert session.auth_user == "tmp1"
        assert session.auth_user is ALLOW

    def test_session(self):
        session = AuthSession("user1")
        assert session.auth_user == "user1"
        session.su("user2")
        assert session.auth_user == "user2"
        with session.su("tmp"):
            assert session.auth_user == "tmp"
        assert session.auth_user == "user2"


class TestScopedSessionSU:
    def test_scoped_session(self):
        session = scoped_session(sessionmaker(class_=AuthSession,
                                              query_cls=AuthQuery))
        session().su(None)
        with pytest.raises(AttributeError):
            session.su(None)

    def test_instrument_scoped_session(self):
        session = scoped_session(sessionmaker(class_=AuthSession,
                                              query_cls=AuthQuery))
        instrument_scoped_session(scoped_session)
        session.su(None)
