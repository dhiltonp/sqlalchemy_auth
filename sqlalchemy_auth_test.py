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


# test - auth query filters - one class, two class, single attributes
class TestAuthBaseFilters:
    class Data(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "data"

        id = Column(Integer, primary_key=True)
        owner = Column(Integer)
        data = Column(String)

        @staticmethod
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
        query = session.query(self.Data)
        assert(query.count() == 6)

    def test_full_object(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            query = session.query(self.Data)
            assert (query.count() == i)

    def test_partial_object(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            query = session.query(self.Data.data)
            assert (itercount(query) == i)
            assert (query.count() == i)

    def test_two_partial_objects(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            query = session.query(self.Data.data, self.Data.id)
            assert (itercount(query) == i)
            assert (query.count() == i)

    def test_mutation(self):
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            query = session.query(self.Data.data)
            statement1 = str(query.statement)
            assert (itercount(query) == i)
            statement2 = str(query.statement)
            assert (statement1 == statement2)

    def test_alternate_syntax(self):
        query = sqlalchemy_auth.AuthQuery(self.Data, session=self.Session())
        assert (query.count() == 6)
        for i in range(1, 4):
            query = sqlalchemy_auth.AuthQuery(self.Data, session=self.Session(), effective_user=i)
            assert (itercount(query) == i)

    def test_effective_user_change(self):
        # Session level:
        for i in range(1, 4):
            self.Session.configure(effective_user=i)
            session = self.Session()
            query = session.query(self.Data.data)
            assert (itercount(query) == i)

        # session level:
        self.Session.configure()
        session = self.Session()
        for i in range(1, 4):
            session._effective_user = i
            query = session.query(self.Data.data)
            assert (itercount(query) == i)

        # query level:
        self.Session.configure()
        session = self.Session()
        query = session.query(self.Data.data)
        for i in range(1, 4):
            query._effective_user = i
            assert (itercount(query) == i)

    def test_update(self):
        self.Session.configure(effective_user=None)
        session = self.Session()

        # B->D
        bvals = session.query(self.Data.data).filter(self.Data.data == "B")
        assert(bvals.count()==2) # there are 2 Bs
        bvals._effective_user=2
        assert (bvals.count() == 1) # one owned by user 2
        changed = bvals.update({self.Data.data:"D"})
        assert (changed == 1) # the other is not changed
        bvals._effective_user = None
        assert (bvals.count() == 1)

        # D->B
        # undo the changes we've performed.
        changed = session.query(self.Data.data).filter(self.Data.data == "D").update({self.Data.data:"B"})
        assert(changed == 1)


def itercount(query):
    count = 0
    for item in query.all():
        count += 1
    return count

# TODO: test more complex queries (Base.attr, Base2.attr):
#  grep "[^a-zA-Z_]query(" * -r | grep -v "query([a-zA-Z_.]*)" | grep -v omni | less
# TODO: test joins:
# for employer in DBSession.query(Entity).outerjoin(User.__table__, Entity.id == User.id).filter(


# test - auth query filters - one class, two class, join, single attributes
class TestJoin:
    class Company(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "company"

        id = Column(Integer, primary_key=True)
        name = Column(String)

        @staticmethod
        def add_auth_filters(query, effective_user):
            #TODO: query isn't guaranteed to run on Company; it may be User (or vice-versa). How to specify?
            return query.filter_by(id=effective_user.company)


    class User(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "user"

        id = Column(Integer, primary_key=True)
        company = Column(Integer)
        name = Column(String)

        @staticmethod
        def add_auth_filters(query, effective_user):
            return query.filter_by(company=effective_user.company)

    engine = create_engine('sqlite:///:memory:', echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(effective_user=None)
    session = Session()

    session.add(Company(name="A"))
    session.add(Company(name="B"))
    session.add(Company(name="C"))

    session.add(User(company=1, name="a"))
    session.add(User(company=2, name="a"))
    session.add(User(company=2, name="b"))
    session.add(User(company=3, name="a"))
    session.add(User(company=3, name="b"))
    session.add(User(company=3, name="c"))

    session.commit()

    user1a = session.query(User).filter(User.company == 1, User.name == "a").one()
    user2a = session.query(User).filter(User.company == 2, User.name == "a").one()

    def test_state(self):
        self.Session.configure(effective_user=None)
        session = self.Session()
        query = session.query(self.Company)
        assert(query.count() == 3)
        query = session.query(self.User)
        assert(query.count() == 6)

    def test_company_filter(self):
        self.Session.configure(effective_user=self.user2a)
        session = self.Session()
        query = session.query(self.User)
        assert(query.count() == 2)
        query = session.query(self.Company)
        assert(query.count() == 1)

    def test_join(self):
        self.Session.configure(effective_user=self.user2a)
        session = self.Session()
        # TODO: filtering is only working against the first class...
        query = session.query(self.User.name, self.Company.name)
        for result in query.all():
            print(result)
        #assert (query.count() == 2)
        query = session.query(self.Company.name, self.User.name)
        for result in query.all():
            print(result)
        assert (query.count() == 2)
