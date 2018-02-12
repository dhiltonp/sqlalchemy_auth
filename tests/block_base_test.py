import pytest
from unittest.mock import Mock
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import ACTIVE, CLOSED

from sqlalchemy_auth import AuthSession, AuthQuery, ALLOW, AuthException, BlockBase


class TestBypassBlock:
    class BlockedData(BlockBase):
        def __init__(self):
            self._session = Mock()
            self._session.transaction._state = ACTIVE
            self._session.badge = None

    def test_stub_defaults(self):
        blocked_data = self.BlockedData()
        assert not blocked_data._bypass_block()

    def test_no_transaction(self):
        blocked_data = self.BlockedData()
        del blocked_data._session.transaction
        assert blocked_data._bypass_block()

    def test_transaction_not_active(self):
        blocked_data = self.BlockedData()
        blocked_data._session.transaction._state = CLOSED
        assert blocked_data._bypass_block()

    def test_allow(self):
        blocked_data = self.BlockedData()
        blocked_data._session.badge = ALLOW
        assert blocked_data._bypass_block()


# test attribute access - block read, write, both, neither
class TestAuthBaseAttributes:
    Base = declarative_base(cls=BlockBase)

    class BlockedData(Base):
        __tablename__ = "blockeddata"

        id = Column(Integer, primary_key=True)
        allowed_data = Column(String)
        blocked_read = Column(String)
        blocked_write = Column(String)
        blocked_both = Column(String)

        def _blocked_read_attributes(self, badge):
            return ["blocked_read", "blocked_both"]

        def _blocked_write_attributes(self, badge):
            return ["blocked_write", "blocked_both"]

    def create_blocked_data(self):
        engine = create_engine("sqlite:///:memory:")#, echo=True)
        self.BlockedData.__table__.create(bind=engine)

        Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
        Session.configure(badge=ALLOW)
        session = Session()

        session.add(self.BlockedData(allowed_data="This is ok", blocked_read="do not allow reads",
                                     blocked_write="do not allow writes", blocked_both="do not allow"))
        session.commit()

        return session.query(self.BlockedData).first()

    def test_allowed(self):
        blocked_data = self.create_blocked_data()
        # ALLOW access
        blocked_data._session.badge = ALLOW
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

        # _auth_settings is set, blocks active
        blocked_data._session.badge = 1
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

    def test_blocked_read(self):
        blocked_data = self.create_blocked_data()
        blocked_data._session.badge = ALLOW
        val = blocked_data.blocked_read
        blocked_data.blocked_read = val

        blocked_data._session.badge = 1
        with pytest.raises(AuthException):
            val = blocked_data.blocked_read
        blocked_data.blocked_read = val

    def test_blocked_write(self):
        blocked_data = self.create_blocked_data()
        blocked_data._session.badge = ALLOW
        val = blocked_data.blocked_write
        blocked_data.blocked_write = val

        blocked_data._session.badge = 1
        val = blocked_data.blocked_write
        with pytest.raises(AuthException):
            blocked_data.blocked_write = "value"

        blocked_data._session.badge = 1
        assert blocked_data.blocked_write != "value"

    def test_blocked_both(self):
        blocked_data = self.create_blocked_data()
        blocked_data._session.badge = ALLOW
        val = blocked_data.blocked_both
        blocked_data.blocked_both = val

        blocked_data._session.badge = 1
        with pytest.raises(AuthException):
            val = blocked_data.blocked_both
        with pytest.raises(AuthException):
            blocked_data.blocked_both = "value"

        blocked_data._session.badge = ALLOW
        assert blocked_data.blocked_write != "value"


class TestGetAttributes:
    Base = declarative_base(cls=BlockBase)

    class AttributeCheck(Base):
        __tablename__ = "attributecheck"

        id = Column(Integer, primary_key=True)
        owner = Column(String)
        data = Column(String)
        secret = Column(String)

        def _blocked_read_attributes(self, badge):
            return ["secret"]

        def _blocked_write_attributes(self, badge):
            return ["id", "owner"]

    def create_attribute_check(self):
        engine = create_engine("sqlite:///:memory:")#, echo=True)
        self.AttributeCheck.__table__.create(bind=engine)

        Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
        Session.configure(badge=1)
        session = Session()

        session.add(self.AttributeCheck(owner="alice", data="bicycle", secret="clover"))

        session.commit()

        return session.query(self.AttributeCheck).first()

    def test_readable_attrs(self):
        a = self.create_attribute_check()
        attrs = a.readable_attrs()
        assert len(attrs) == 3
        for v in ["id", "owner", "data"]:
            assert v in attrs

    def test_writable_attrs(self):
        a = self.create_attribute_check()
        attrs = a.writable_attrs()
        assert len(attrs) == 2
        for v in ["data", "secret"]:
            assert v in attrs

    def test_read_blocked_attrs(self):
        a = self.create_attribute_check()
        attrs = a.read_blocked_attrs()
        assert len(attrs) == 1
        assert "secret" in attrs

    def test_write_blocked_attrs(self):
        a = self.create_attribute_check()
        attrs = a.write_blocked_attrs()
        assert len(attrs) == 2
        for v in ["id", "owner"]:
            assert v in attrs


def test_read_in_blocked_methods():
    Base = declarative_base(cls=BlockBase)

    class AllowedCheck(Base):
        __tablename__ = "allowedcheck"

        id = Column(Integer, primary_key=True)
        blocked_read = Column(String)

        def _blocked_read_attributes(self, badge):
            self.blocked_read
            return ["blocked_read"]

        def _blocked_write_attributes(self, badge):
            self.blocked_read
            return []

    engine = create_engine("sqlite:///:memory:")#, echo=True)
    AllowedCheck.__table__.create(bind=engine)

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(badge=1)
    session = Session()

    session.add(AllowedCheck(blocked_read="bicycle"))
    session.commit()
    a = session.query(AllowedCheck).first()

    # actual test
    attrs = a.write_blocked_attrs()
    attrs = a.read_blocked_attrs()
