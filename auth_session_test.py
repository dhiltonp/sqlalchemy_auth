import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from sqlalchemy_auth import AuthSession, AuthQuery, ALLOW, instrument_scoped_session
from sqlalchemy_auth.utils import _Settings
from sqlalchemy_auth.auth_session import _UserContext


class TestUserContext:
    def test_context(self):
        settings = _Settings()
        assert settings.user is ALLOW
        with _UserContext(settings):
            settings.user = "tmp1"
            with _UserContext(settings):
                assert settings.user == "tmp1"
                settings.user = "tmp2"
            assert settings.user == "tmp1"
        assert settings.user is ALLOW

    def test_session(self):
        session = AuthSession("user1")
        assert session._auth_settings.user == "user1"
        session.su("user2")
        assert session._auth_settings.user == "user2"
        with session.su("tmp"):
            assert session._auth_settings.user == "tmp"
        assert session._auth_settings.user == "user2"


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
