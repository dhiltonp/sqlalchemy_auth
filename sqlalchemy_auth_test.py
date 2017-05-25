#!/bin/python

import pytest
import sqlalchemy_auth
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import Column, Integer, String, ForeignKey


Base = declarative_base(cls=sqlalchemy_auth.AuthBase)


# test attribute access - block read, write, both, neither
class TestAuthBaseAttributes:
    class BlockedData(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "blockeddata"

        id = Column(Integer, primary_key=True)
        allowed_data = Column(String)
        blocked_read = Column(String)
        blocked_write = Column(String)
        blocked_both = Column(String)

        def _blocked_read_attributes(self, effective_user):
            return ["blocked_read", "blocked_both"]

        def _blocked_write_attributes(self, effective_user):
            return ["blocked_write", "blocked_both"]


    def create_blocked_data(self):
        engine = create_engine('sqlite:///:memory:')#, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
        Session.configure(effective_user=None)
        session = Session()

        session.add(self.BlockedData(allowed_data="This is ok", blocked_read="do not allow reads",
                                     blocked_write="do not allow writes", blocked_both="do not allow"))
        session.commit()

        return session.query(self.BlockedData).first()

    def test_allowed(self):
        blocked_data = self.create_blocked_data()
        # bypassing blocks:
        blocked_data._effective_user = None
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

        # _effective_user is set, blocks active
        blocked_data._effective_user = 1
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

    def test_blocked_read(self):
        blocked_data = self.create_blocked_data()
        blocked_data._effective_user = None
        val = blocked_data.blocked_read
        blocked_data.blocked_read = val

        blocked_data._effective_user = 1
        with pytest.raises(sqlalchemy_auth.AuthException):
            val = blocked_data.blocked_read
        blocked_data.blocked_read = val

    def test_blocked_write(self):
        blocked_data = self.create_blocked_data()
        blocked_data._effective_user = None
        val = blocked_data.blocked_write
        blocked_data.blocked_write = val

        blocked_data._effective_user = 1
        val = blocked_data.blocked_write
        with pytest.raises(sqlalchemy_auth.AuthException):
            blocked_data.blocked_write = "value"
        assert(blocked_data.blocked_write != "value")

    def test_blocked_both(self):
        blocked_data = self.create_blocked_data()
        blocked_data._effective_user = None
        val = blocked_data.blocked_both
        blocked_data.blocked_both = val

        blocked_data._effective_user = 1
        with pytest.raises(sqlalchemy_auth.AuthException):
            val = blocked_data.blocked_both
        with pytest.raises(sqlalchemy_auth.AuthException):
            blocked_data.blocked_both = "value"

        blocked_data._effective_user = None
        assert(blocked_data.blocked_write != "value")


class TestGetAttributes:
    class AttributeCheck(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "attributecheck"

        id = Column(Integer, primary_key=True)
        owner = Column(String)
        data = Column(String)
        secret = Column(String)

        def _blocked_read_attributes(self, _effective_user):
            return ["secret"]

        def _blocked_write_attributes(self, _effective_user):
            return ["id", "owner"]

    def create_attribute_check(self):
        engine = create_engine('sqlite:///:memory:')#, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
        Session.configure(effective_user=1)
        session = Session()

        session.add(self.AttributeCheck(owner="alice", data="bicycle", secret="clover"))

        session.commit()

        return session.query(self.AttributeCheck).first()

    def test_get_read_attributes(self):
        a = self.create_attribute_check()
        attrs = a.get_read_attributes()
        assert(len(attrs) == 3)
        for v in ["id", "owner", "data"]:
            assert(v in attrs)

    def test_get_write_attributes(self):
        a = self.create_attribute_check()
        attrs = a.get_write_attributes()
        assert (len(attrs) == 2)
        for v in ["data", "secret"]:
            assert (v in attrs)

    def test_get_blocked_read_attributes(self):
        a = self.create_attribute_check()
        attrs = a.get_blocked_read_attributes()
        assert(len(attrs) == 1)
        assert("secret" in attrs)


# test - auth query filters - one class, two class, join, single attributes
class TestAuthBaseFilters:
    class Data(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "data"

        id = Column(Integer, primary_key=True)
        owner = Column(Integer)
        data = Column(String)

        def add_auth_filters(query, _effective_user):
            return query.filter_by(owner=_effective_user)

    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(effective_user=None)
    session = Session()

    session.add(Data(owner=1, data="A"))
    session.add(Data(owner=2, data="A"))
    session.add(Data(owner=2, data="B"))
    session.add(Data(owner=3, data="A"))
    session.add(Data(owner=3, data="B"))
    session.add(Data(owner=3, data="C"))

    session.commit()

    def test_bypass(self):
        self.Session.configure(effective_user=None)
        session = self.Session()
        result = session.query(self.Data)
        assert(result.count() == 6)

    def test_full_object(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            result = session.query(self.Data)
            assert (result.count() == i)

    def test_partial_object(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            result = session.query(self.Data.data)
            assert (itercount(result) == i)
            assert (result.count() == i)

    def test_two_partial_objects(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            result = session.query(self.Data.data, self.Data.id)
            assert (itercount(result) == i)
            assert (result.count() == i)

    def test_mutation(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            result = session.query(self.Data.data)
            statement1 = str(result.statement)
            assert (itercount(result) == i)
            statement2 = str(result.statement)
            assert (statement1 == statement2)


def itercount(query):
    count = 0
    for item in query.all():
        count += 1
    return count

# TODO: test more complex queries (Base.attr, Base2.attr):
#  grep "[^a-zA-Z_]query(" * -r | grep -v "query([a-zA-Z_.]*)" | grep -v omni | less
# TODO: test joins:
# for employer in DBSession.query(Entity).outerjoin(User.__table__, Entity.id == User.id).filter(

