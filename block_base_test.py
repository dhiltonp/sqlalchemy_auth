import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy_auth import AuthSession, AuthQuery, ALLOW, AuthException, BlockBase

Base = declarative_base(cls=BlockBase)


# test attribute access - block read, write, both, neither
class TestAuthBaseAttributes:
    class BlockedData(Base, BlockBase):
        __tablename__ = "blockeddata"

        id = Column(Integer, primary_key=True)
        allowed_data = Column(String)
        blocked_read = Column(String)
        blocked_write = Column(String)
        blocked_both = Column(String)

        def _blocked_read_attributes(self, user):
            return ["blocked_read", "blocked_both"]

        def _blocked_write_attributes(self, user):
            return ["blocked_write", "blocked_both"]

    def create_blocked_data(self):
        engine = create_engine('sqlite:///:memory:')#, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
        Session.configure(user=ALLOW)
        session = Session()

        session.add(self.BlockedData(allowed_data="This is ok", blocked_read="do not allow reads",
                                     blocked_write="do not allow writes", blocked_both="do not allow"))
        session.commit()

        return session.query(self.BlockedData).first()

    def test_allowed(self):
        blocked_data = self.create_blocked_data()
        # ALLOW access
        blocked_data._auth_settings.user = ALLOW
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

        # _auth_settings is set, blocks active
        blocked_data._auth_settings.user = 1
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

    def test_blocked_read(self):
        blocked_data = self.create_blocked_data()
        blocked_data._auth_settings.user = ALLOW
        val = blocked_data.blocked_read
        blocked_data.blocked_read = val

        blocked_data._auth_settings.user = 1
        with pytest.raises(AuthException):
            val = blocked_data.blocked_read
        blocked_data.blocked_read = val

    def test_blocked_write(self):
        blocked_data = self.create_blocked_data()
        blocked_data._auth_settings.user = ALLOW
        val = blocked_data.blocked_write
        blocked_data.blocked_write = val

        blocked_data._auth_settings.user = 1
        val = blocked_data.blocked_write
        with pytest.raises(AuthException):
            blocked_data.blocked_write = "value"

        blocked_data._auth_settings.user = 1
        assert blocked_data.blocked_write != "value"

    def test_blocked_both(self):
        blocked_data = self.create_blocked_data()
        blocked_data._auth_settings.user = ALLOW
        val = blocked_data.blocked_both
        blocked_data.blocked_both = val

        blocked_data._auth_settings.user = 1
        with pytest.raises(AuthException):
            val = blocked_data.blocked_both
        with pytest.raises(AuthException):
            blocked_data.blocked_both = "value"

        blocked_data._auth_settings.user = ALLOW
        assert blocked_data.blocked_write != "value"


class TestGetAttributes:
    class AttributeCheck(Base, BlockBase):
        __tablename__ = "attributecheck"

        id = Column(Integer, primary_key=True)
        owner = Column(String)
        data = Column(String)
        secret = Column(String)

        def _blocked_read_attributes(self, user):
            return ["secret"]

        def _blocked_write_attributes(self, user):
            return ["id", "owner"]

    def create_attribute_check(self):
        engine = create_engine('sqlite:///:memory:')#, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
        Session.configure(user=1)
        session = Session()

        session.add(self.AttributeCheck(owner="alice", data="bicycle", secret="clover"))

        session.commit()

        return session.query(self.AttributeCheck).first()

    def test_get_read_attributes(self):
        a = self.create_attribute_check()
        attrs = a.get_read_attributes()
        assert len(attrs) == 3
        for v in ["id", "owner", "data"]:
            assert v in attrs

    def test_get_write_attributes(self):
        a = self.create_attribute_check()
        attrs = a.get_write_attributes()
        assert len(attrs) == 2
        for v in ["data", "secret"]:
            assert v in attrs

    def test_get_blocked_read_attributes(self):
        a = self.create_attribute_check()
        attrs = a.get_blocked_read_attributes()
        assert len(attrs) == 1
        assert "secret" in attrs

