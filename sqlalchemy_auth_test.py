#!/bin/python

import pytest
import sqlalchemy_auth
from sqlalchemy import create_engine, ForeignKey, Table, literal
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship

from sqlalchemy import Column, Integer, String


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

        def _blocked_read_attributes(self, user):
            return ["blocked_read", "blocked_both"]

        def _blocked_write_attributes(self, user):
            return ["blocked_write", "blocked_both"]

    def create_blocked_data(self):
        engine = create_engine('sqlite:///:memory:')#, echo=True)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
        Session.configure(user=sqlalchemy_auth.ALLOW)
        session = Session()

        session.add(self.BlockedData(allowed_data="This is ok", blocked_read="do not allow reads",
                                     blocked_write="do not allow writes", blocked_both="do not allow"))
        session.commit()

        return session.query(self.BlockedData).first()

    def test_allowed(self):
        blocked_data = self.create_blocked_data()
        # ALLOW access
        blocked_data._auth_settings.user = sqlalchemy_auth.ALLOW
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

        # _auth_settings is set, blocks active
        blocked_data._auth_settings.user = 1
        val = blocked_data.allowed_data
        blocked_data.allowed_data = val

    def test_blocked_read(self):
        blocked_data = self.create_blocked_data()
        blocked_data._auth_settings.user = sqlalchemy_auth.ALLOW
        val = blocked_data.blocked_read
        blocked_data.blocked_read = val

        blocked_data._auth_settings.user = 1
        with pytest.raises(sqlalchemy_auth.AuthException):
            val = blocked_data.blocked_read
        blocked_data.blocked_read = val

    def test_blocked_write(self):
        blocked_data = self.create_blocked_data()
        blocked_data._auth_settings.user = sqlalchemy_auth.ALLOW
        val = blocked_data.blocked_write
        blocked_data.blocked_write = val

        blocked_data._auth_settings.user = 1
        val = blocked_data.blocked_write
        with pytest.raises(sqlalchemy_auth.AuthException):
            blocked_data.blocked_write = "value"

        blocked_data._auth_settings.user = 1
        assert blocked_data.blocked_write != "value"

    def test_blocked_both(self):
        blocked_data = self.create_blocked_data()
        blocked_data._auth_settings.user = sqlalchemy_auth.ALLOW
        val = blocked_data.blocked_both
        blocked_data.blocked_both = val

        blocked_data._auth_settings.user = 1
        with pytest.raises(sqlalchemy_auth.AuthException):
            val = blocked_data.blocked_both
        with pytest.raises(sqlalchemy_auth.AuthException):
            blocked_data.blocked_both = "value"

        blocked_data._auth_settings.user = sqlalchemy_auth.ALLOW
        assert blocked_data.blocked_write != "value"


class TestGetAttributes:
    class AttributeCheck(Base, sqlalchemy_auth.AuthBase):
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

        Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
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


# test - auth query filters - one class, two class, single attributes
class TestAuthBaseFilters:
    class Data(Base, sqlalchemy_auth.AuthBase):
        __tablename__ = "data"

        id = Column(Integer, primary_key=True)
        owner = Column(Integer)
        data = Column(String)

        @classmethod
        def add_auth_filters(cls, query, user):
            return query.filter(cls.owner == user)

    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(user=sqlalchemy_auth.ALLOW)
    session = Session()

    session.add(Data(owner=1, data="A"))
    session.add(Data(owner=2, data="A"))
    session.add(Data(owner=2, data="B"))
    session.add(Data(owner=3, data="A"))
    session.add(Data(owner=3, data="B"))
    session.add(Data(owner=3, data="C"))

    session.commit()

    def test_bypass(self):
        session = self.Session()
        query = session.query(self.Data)
        assert itercount(query) == 6

    def test_full_object(self):
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data)
            assert itercount(query) == i

    def test_partial_object(self):
        session = self.Session()
        for i in range(1, 4):
            session.su(user=i)
            query = session.query(self.Data.data)
            assert itercount(query) == i
            assert itercount(query) == i

    def test_two_partial_objects(self):
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data.data, self.Data.id)
            assert itercount(query) == i
            assert itercount(query) == i

    def test_mutation(self):
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data.data)
            statement1 = str(query.statement)
            assert itercount(query) == i
            statement2 = str(query.statement)
            assert statement1 == statement2

    def test_user_change(self):
        # Session level:
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data.data)
            assert itercount(query) == i

        # session level:
        self.Session.configure()
        session = self.Session()
        for i in range(1, 4):
            session.su(user=i)
            query = session.query(self.Data.data)
            assert itercount(query) == i

        # query level:
        self.Session.configure()
        session = self.Session()
        for i in range(1, 4):
            session.su(user=i)
            query = session.query(self.Data.data)
            assert itercount(query) == i

    def test_update(self):
        self.Session.configure(user=sqlalchemy_auth.ALLOW)
        session = self.Session()

        # B->D
        bvals = session.query(self.Data.data).filter(self.Data.data == "B")
        assert itercount(bvals) == 2  # there are 2 Bs
        session.su(2)
        assert itercount(bvals) == 1  # one owned by user 2
        changed = bvals.update({self.Data.data: "D"})
        assert changed == 1  # the other is not changed
        session.su(sqlalchemy_auth.ALLOW)
        assert itercount(bvals) == 1

        # D->B
        # undo the changes we've performed.
        changed = session.query(self.Data.data).filter(self.Data.data == "D").update({self.Data.data: "B"})
        assert changed == 1

    def test_delete(self):
        self.Session.configure(user=sqlalchemy_auth.ALLOW)
        session = self.Session()

        bvals = session.query(self.Data.data).filter(self.Data.data == "B")
        assert itercount(bvals) == 2  # there are 2 Bs
        changed = bvals.delete()
        assert changed == 2
        session.rollback()

        session.su(2)
        assert itercount(bvals) == 1  # one owned by user 2
        changed = bvals.delete()
        assert changed == 1  # the other is not changed
        session.rollback()

        session.su(sqlalchemy_auth.DENY)
        with pytest.raises(sqlalchemy_auth.AuthException):
            session.query(self.Data).delete()

    def test_DENY(self):
        self.Session.configure(user=sqlalchemy_auth.DENY)
        session = self.Session()

        with pytest.raises(sqlalchemy_auth.AuthException):
            session.query(self.Data).all()

    def test_independent_session_user(self):
        # user is independent of sessions
        self.Session.configure(user=2)
        session = self.Session()
        filter_a = session.query(self.Data).filter(self.Data.data == "A").one()

        self.Session.configure(user=sqlalchemy_auth.ALLOW)
        session = self.Session()
        allow_a = session.query(self.Data).filter(self.Data.data == "A", self.Data.owner == 2).one()

        assert filter_a._auth_settings.user == 2
        assert allow_a._auth_settings.user == sqlalchemy_auth.ALLOW

    def test_consistent_session_user(self):
        self.Session.configure(user=1)
        session = self.Session()
        a = session.query(self.Data).filter(self.Data.data == "A").one()
        session.su(2)
        b = session.query(self.Data).filter(self.Data.data == "B").one()

        assert a._auth_settings.user == 2
        assert b._auth_settings.user == 2

    def test_slice(self):
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data).slice(0, 2)
            assert itercount(query) == min(i, 2)

    def test_limit(self):
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data).limit(2)
            assert itercount(query) == min(i, 2)

    def test_offset(self):
        for i in range(1, 4):
            self.Session.configure(user=i)
            session = self.Session()
            query = session.query(self.Data).offset(1)
            assert itercount(query) == i-1

    def test_with_session(self):
        self.Session.configure(user=1)
        session1 = self.Session()
        query = session1.query(self.Data)
        assert itercount(query) == 1

        self.Session.configure(user=2)
        session2 = self.Session()
        assert itercount(query.with_session(session2)) == 2

        assert itercount(query) == 1

    def test_select_from(self):
        session = self.Session()
        for i in range(1, 4):
            with session.su(i):
                count1 = itercount(session.query(literal(True)).select_from(self.Data))
                count2 = itercount(session.query(self.Data))
                assert count1 == count2
                assert count2 == i


def itercount(query):
    count = len(query.all())
    assert query.count() == count
    return count


company_resource_association = Table('company_resource_association', Base.metadata,
                                     Column('company_id', Integer, ForeignKey('company.id')),
                                     Column('resource_id', Integer, ForeignKey('sharedresource.id')))


class Company(Base, sqlalchemy_auth.AuthBase):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    users = relationship("User")
    sharedresources = relationship("SharedResource",
                                   secondary=company_resource_association,
                                   back_populates="companies")

    @classmethod
    def add_auth_filters(cls, query, user):
        # return query.filter_by(id=user.company_id)
        return query.filter(cls.id == user.company_id)


class User(Base, sqlalchemy_auth.AuthBase):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey('company.id'))
    company = relationship("Company", back_populates="users")

    @classmethod
    def add_auth_filters(cls, query, user):
        # return query.filter_by(company=user.company)
        return query.filter(cls.company_id == user.company_id)


class SharedResource(Base, sqlalchemy_auth.AuthBase):
    __tablename__ = "sharedresource"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    companies = relationship("Company",
                             secondary=company_resource_association,
                             back_populates="sharedresources")


class Widget(Base, sqlalchemy_auth.AuthBase):
    __tablename__ = "widget"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey('company.id'))
    company = relationship("Company", backref="widgets")


# test - auth query filters - one class, two class, join, single attributes
class TestInteractions:
    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(user=sqlalchemy_auth.ALLOW)
    session = Session()

    session.add(Company(name="A"))
    session.add(Company(name="B"))
    session.add(Company(name="C"))

    session.add(User(company_id=1, name="a"))
    session.add(User(company_id=2, name="a"))
    session.add(User(company_id=2, name="b"))
    session.add(User(company_id=3, name="a"))
    session.add(User(company_id=3, name="b"))
    session.add(User(company_id=3, name="c"))

    session.add(Widget(company_id=1, name="widgetA1"))
    session.add(Widget(company_id=1, name="widgetA2"))
    session.add(Widget(company_id=2, name="widgetB1"))
    session.add(Widget(company_id=2, name="widgetB2"))

    session.commit()

    user1a = session.query(User).filter(User.company_id == 1, User.name == "a").one()
    user2a = session.query(User).filter(User.company_id == 2, User.name == "a").one()

    def test_orthogonal_class(self):
        self.Session.configure(user=self.user1a)
        session = self.Session()
        query = session.query(Widget).join(Company)
        assert itercount(query) == 2

    def test_state(self):
        self.Session.configure(user=sqlalchemy_auth.ALLOW)
        session = self.Session()
        query = session.query(Company)
        assert itercount(query) == 3
        query = session.query(User)
        assert itercount(query) == 6

    def test_company_filter(self):
        self.Session.configure(user=self.user2a)
        session = self.Session()
        query = session.query(User)
        assert itercount(query) == 2
        query = session.query(Company)
        assert itercount(query) == 1

    def test_join(self):
        self.Session.configure(user=self.user2a)
        session = self.Session()
        query = session.query(User.name, Company.name)
        assert itercount(query) == 2
        query = session.query(Company.name, User.name)
        assert itercount(query) == 2
        assert itercount(query.filter(User.name == self.user2a.name)) == 1

    def test_distinct(self):
        from sqlalchemy import distinct
        self.Session.configure(user=self.user2a)
        session = self.Session()
        query = session.query(User.company_id)
        assert itercount(query) == 2
        query = session.query(distinct(User.company_id))
        assert itercount(query) == 1

    def test_max(self):
        from sqlalchemy import func
        self.Session.configure(user=self.user2a)
        session = self.Session()
        query = session.query(func.max(User.id))
        assert itercount(query) == 1
        assert 3 == query.one()[0]

    def test_relationships(self):
        assert self.user1a.company.id == 1
        assert self.user1a.company.users[0] == self.user1a
        assert len(self.user2a.company.users) == 2


class TestSharedResource:
    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(user=sqlalchemy_auth.ALLOW)
    session = Session()

    companyA = Company(name="A")
    companyB = Company(name="B")
    session.add(companyA)
    session.add(companyB)
    session.commit()

    userA = User(name="a", company_id=companyA.id)
    userB = User(name="a", company_id=companyB.id)
    session.add(userA)
    session.add(userB)

    resourceA = SharedResource(name="A")
    resourceA.companies.append(companyA)
    resourceB = SharedResource(name="B")
    resourceB.companies.append(companyB)
    resourceAB = SharedResource(name="AB")
    resourceAB.companies.append(companyA)
    resourceAB.companies.append(companyB)

    session.commit()

    def test_shared_resource(self):
        self.Session.configure(user=self.userA)
        session = self.Session()
        companyA = session.query(Company).one()
        assert len(companyA.sharedresources) == 2
        assert itercount(session.query(SharedResource)) == 3
        resourceB = session.query(SharedResource).filter_by(name="B").one()
        assert len(resourceB.companies) == 0
        resourceAB = session.query(SharedResource).filter_by(name="AB").one()
        assert len(resourceAB.companies) == 1


class TestUserContext:
    def test_context(self):
        settings = sqlalchemy_auth._Settings()
        assert settings.user is sqlalchemy_auth.ALLOW
        with sqlalchemy_auth._UserContext(settings):
            settings.user = "tmp1"
            with sqlalchemy_auth._UserContext(settings):
                assert settings.user == "tmp1"
                settings.user = "tmp2"
            assert settings.user == "tmp1"
        assert settings.user is sqlalchemy_auth.ALLOW

    def test_session(self):
        session = sqlalchemy_auth.AuthSession("user1")
        assert session._auth_settings.user == "user1"
        session.su("user2")
        assert session._auth_settings.user == "user2"
        with session.su("tmp"):
            assert session._auth_settings.user == "tmp"
        assert session._auth_settings.user == "user2"


class TestScopedSessionSU:
    def test_scoped_session(self):
        session = scoped_session(sessionmaker(class_=sqlalchemy_auth.AuthSession,
                                              query_cls=sqlalchemy_auth.AuthQuery))
        session().su(None)
        with pytest.raises(AttributeError):
            session.su(None)

    def test_instrument_scoped_session(self):
        session = scoped_session(sessionmaker(class_=sqlalchemy_auth.AuthSession,
                                              query_cls=sqlalchemy_auth.AuthQuery))
        sqlalchemy_auth.instrument_scoped_session(scoped_session)
        session.su(None)


class InsertData(Base, sqlalchemy_auth.AuthBase):
    __tablename__ = "data2"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    def add_auth_insert_data(self, user):
        self.owner = user


# test - auth query inserts
class TestAuthBaseInserts:
    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(user=sqlalchemy_auth.ALLOW)
    session = Session()

    def test_add(self):
        session = self.Session()
        with session.su(10):
            obj = InsertData(data="Insert")
            session.add(obj)
            session.commit()
            assert obj.owner == 10

        with session.su():
            obj = session.query(InsertData).filter(InsertData.owner == 10).one()
            obj.data = "SU Update"
            session.commit()
            assert obj.data == "SU Update"
            assert obj.owner == 10

        with session.su(10):
            obj = session.query(InsertData).filter(InsertData.owner == 10).one()
            obj.data = "Owner Update"
            session.commit()
            assert obj.data == "Owner Update"

        with session.su(20):
            obj.data = "Non-owner Update"
            session.add(obj)
            session.commit()
            assert obj.data == "Non-owner Update"
            assert obj.owner == 10
