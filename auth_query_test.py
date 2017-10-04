import pytest

from sqlalchemy_auth import AuthSession, AuthQuery, AuthBase, AuthException, ALLOW, DENY

from sqlalchemy import create_engine, ForeignKey, Table, literal
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import Column, Integer, String


Base = declarative_base(cls=AuthBase)


def itercount(query):
    count = len(query.all())
    assert query.count() == count
    return count


# test - auth query filters - one class, two class, single attributes
class TestAuthBaseFilters:
    class Data(Base, AuthBase):
        __tablename__ = "data"

        id = Column(Integer, primary_key=True)
        owner = Column(Integer)
        data = Column(String)

        @classmethod
        def add_auth_filters(cls, query, user):
            return query.filter(cls.owner == user)

    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(user=ALLOW)
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
        self.Session.configure(user=ALLOW)
        session = self.Session()

        # B->D
        bvals = session.query(self.Data.data).filter(self.Data.data == "B")
        assert itercount(bvals) == 2  # there are 2 Bs
        session.su(2)
        assert itercount(bvals) == 1  # one owned by user 2
        changed = bvals.update({self.Data.data: "D"})
        assert changed == 1  # the other is not changed
        session.su(ALLOW)
        assert itercount(bvals) == 1

        # D->B
        # undo the changes we've performed.
        changed = session.query(self.Data.data).filter(self.Data.data == "D").update({self.Data.data: "B"})
        assert changed == 1

    def test_delete(self):
        self.Session.configure(user=ALLOW)
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

        session.su(DENY)
        with pytest.raises(AuthException):
            session.query(self.Data).delete()

    def test_DENY(self):
        self.Session.configure(user=DENY)
        session = self.Session()

        with pytest.raises(AuthException):
            session.query(self.Data).all()

    def test_independent_session_user(self):
        # user is independent of sessions
        self.Session.configure(user=2)
        session = self.Session()
        filter_a = session.query(self.Data).filter(self.Data.data == "A").one()

        self.Session.configure(user=ALLOW)
        session = self.Session()
        allow_a = session.query(self.Data).filter(self.Data.data == "A", self.Data.owner == 2).one()

        assert filter_a._auth_settings.user == 2
        assert allow_a._auth_settings.user == ALLOW

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


company_resource_association = Table('company_resource_association', Base.metadata,
                                     Column('company_id', Integer, ForeignKey('company.id')),
                                     Column('resource_id', Integer, ForeignKey('sharedresource.id')))


class Company(Base, AuthBase):
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


class User(Base, AuthBase):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey('company.id'))
    company = relationship("Company", back_populates="users")

    @classmethod
    def add_auth_filters(cls, query, user):
        # return query.filter_by(company=user.company)
        return query.filter(cls.company_id == user.company_id)


class SharedResource(Base, AuthBase):
    __tablename__ = "sharedresource"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    companies = relationship("Company",
                             secondary=company_resource_association,
                             back_populates="sharedresources")


class Widget(Base, AuthBase):
    __tablename__ = "widget"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey('company.id'))
    company = relationship("Company", backref="widgets")


# test - auth query filters - one class, two class, join, single attributes
class TestInteractions:
    engine = create_engine('sqlite:///:memory:')#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(user=ALLOW)
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
        self.Session.configure(user=ALLOW)
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

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(user=ALLOW)
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


class InsertData(Base, AuthBase):
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

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(user=ALLOW)
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