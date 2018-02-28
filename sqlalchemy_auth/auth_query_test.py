import pytest

from sqlalchemy_auth import AuthSession, AuthQuery, AuthBase, AuthException, ALLOW, DENY

from sqlalchemy import create_engine, ForeignKey, Table, literal, func, distinct
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased, subqueryload
from sqlalchemy import Column, Integer, String


Base = declarative_base(cls=AuthBase)


def itercount(query):
    count = len(query.all())
    assert query.count() == count
    return count


class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    @classmethod
    def add_auth_filters(cls, query, badge):
        return query.filter(cls.owner == badge)


# test - auth query filters - one class, two class, single attributes
class TestAuthBaseFilters:
    engine = create_engine("sqlite:///:memory:")#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(badge=ALLOW)
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
        query = session.query(Data)
        assert itercount(query) == 6

    def test_full_object(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data)
            assert itercount(query) == i

    def test_partial_object(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data.data)
            assert itercount(query) == i
            assert itercount(query) == i

    def test_two_partial_objects(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data.data, Data.id)
            assert itercount(query) == i
            assert itercount(query) == i

    def test_mutation(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data.data)
            statement1 = str(query.statement)
            assert itercount(query) == i
            statement2 = str(query.statement)
            assert statement1 == statement2

    def test_update(self):
        session = self.Session()

        # B->D
        bvals = session.query(Data.data).filter(Data.data == "B")
        assert itercount(bvals) == 2  # there are 2 Bs
        session.badge = 2
        assert itercount(bvals) == 1  # one owned by badge 2
        changed = bvals.update({Data.data: "D"})
        assert changed == 1  # the other is not changed
        session.badge = ALLOW
        assert itercount(bvals) == 1

        # D->B
        # undo the changes we've performed.
        changed = session.query(Data.data).filter(Data.data == "D").update({Data.data: "B"})
        assert changed == 1

    def test_delete(self):
        session = self.Session()

        bvals = session.query(Data.data).filter(Data.data == "B")
        assert itercount(bvals) == 2  # there are 2 Bs
        changed = bvals.delete()
        assert changed == 2
        session.rollback()

        session.badge = 2
        assert itercount(bvals) == 1  # one owned by badge 2
        changed = bvals.delete()
        assert changed == 1  # the other is not changed
        session.rollback()

        session.badge = DENY
        with pytest.raises(AuthException):
            session.query(Data).delete()

    def test_DENY(self):
        session = self.Session()
        session.badge = DENY

        with pytest.raises(AuthException):
            session.query(Data).all()

    def test_slice(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data).slice(0, 2)
            assert itercount(query) == min(i, 2)

    def test_limit(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data).limit(2)
            assert itercount(query) == min(i, 2)

    def test_offset(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            query = session.query(Data).offset(1)
            assert itercount(query) == i-1

    def test_with_session(self):
        session1 = self.Session()
        session1.badge = 1
        query = session1.query(Data)
        assert itercount(query) == 1

        session2 = self.Session()
        session2.badge = 2
        assert itercount(query.with_session(session2)) == 2

        assert itercount(query) == 1

    def test_select_from(self):
        session = self.Session()
        for i in range(1, 4):
            session.badge = i
            count1 = itercount(session.query(literal(True)).select_from(Data))
            count2 = itercount(session.query(Data))
            assert count1 == count2
            assert count2 == i


company_resource_association = Table("company_resource_association", Base.metadata,
                                     Column("company_id", Integer, ForeignKey("company.id")),
                                     Column("resource_id", Integer, ForeignKey("sharedresource.id")))


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    users = relationship("User")
    sharedresources = relationship("SharedResource",
                                   secondary=company_resource_association,
                                   back_populates="companies")

    @classmethod
    def add_auth_filters(cls, query, badge):
        return query.filter_by(id=badge.company_id)


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey("company.id"))
    company = relationship("Company", back_populates="users")

    @classmethod
    def add_auth_filters(cls, query, badge):
        return query.filter(cls.company_id == badge.company_id)


class SharedResource(Base):
    __tablename__ = "sharedresource"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    companies = relationship("Company",
                             secondary=company_resource_association,
                             back_populates="sharedresources")


class Widget(Base):
    __tablename__ = "widget"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey("company.id"))
    company = relationship("Company", backref="widgets")


# test - auth query filters - one class, two class, join, single attributes
class TestInteractions:
    engine = create_engine("sqlite:///:memory:")#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(badge=ALLOW)
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
        session = self.Session()
        session.badge = self.user1a
        query = session.query(Widget).join(Company)
        assert itercount(query) == 2

    def test_aliased_class_in_from(self):
        session = self.Session()

        session.badge = self.user1a
        employer = aliased(Company, name="employer")
        query = session.query(Widget, employer.name).join(employer)

        assert itercount(query) == 2

    def test_state(self):
        session = self.Session()
        query = session.query(Company)
        assert itercount(query) == 3
        query = session.query(User)
        assert itercount(query) == 6

    def test_company_filter(self):
        session = self.Session()
        session.badge = self.user2a
        query = session.query(User)
        assert itercount(query) == 2
        query = session.query(Company)
        assert itercount(query) == 1

    def test_join(self):
        session = self.Session()
        session.badge = self.user2a
        query = session.query(User.name, Company.name)
        assert itercount(query) == 2
        query = session.query(Company.name, User.name)
        assert itercount(query) == 2
        assert itercount(query.filter(User.name == self.user2a.name)) == 1

    def test_distinct(self):
        session = self.Session()
        session.badge = self.user2a
        query = session.query(User.company_id)
        assert itercount(query) == 2
        query = session.query(distinct(User.company_id))
        assert itercount(query) == 1

    def test_max(self):
        session = self.Session()
        session.badge = self.user2a
        query = session.query(func.max(User.id))
        assert itercount(query) == 1
        assert 3 == query.one()[0]

    def test_relationships(self):
        assert self.user1a.company.id == 1
        assert self.user1a.company.users[0] == self.user1a
        assert len(self.user2a.company.users) == 2

    def test_subqueryload(self):
        session = self.Session()
        q = session.query(Company).options(subqueryload(Company.users))
        assert q.count() == 3
        for company in q:
            assert len(company.users) == company.id


class TestSharedResource:
    def populate_db(self):
        engine = create_engine("sqlite:///:memory:")#, echo=True)
        Base.metadata.create_all(engine)

        #enable_baked_queries=False,
        Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
        Session.configure(badge=ALLOW)
        session = Session()

        companyA = Company(name="A")
        companyB = Company(name="B")
        session.add(companyA)
        session.add(companyB)
        session.commit()

        userA = User(name="a", company_id=companyA.id)
        userB = User(name="b", company_id=companyB.id)
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

        return Session()

    def test_shared_resource(self):
        session = self.populate_db()

        userA = session.query(User).filter_by(name="a").one()
        session.badge = userA

        companyA = session.query(Company).one()
        assert len(companyA.sharedresources) == 2
        assert itercount(session.query(SharedResource)) == 3
        resourceB = session.query(SharedResource).filter_by(name="B").one()
        assert len(resourceB.companies) == 0
        resourceAB = session.query(SharedResource).filter_by(name="AB").one()
        assert len(resourceAB.companies) == 1

    def test_baked_relationship_query(self):
        # if these queries are baked, filtering is broken.
        session = self.populate_db()

        userA = session.query(User).filter_by(name="a").one()

        session.badge = userA
        resourceAB = session.query(SharedResource).filter_by(name="AB").one()
        assert len(resourceAB.companies) == 1

        session.badge = ALLOW
        session.expunge_all()
        resourceAB = session.query(SharedResource).filter_by(name="AB").one()
        assert len(resourceAB.companies) == 2


class InsertData(Base):
    __tablename__ = "data2"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    def add_auth_insert_data(self, badge):
        self.owner = badge


# test - auth query inserts
class TestAuthBaseInserts:
    engine = create_engine("sqlite:///:memory:")#, echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
    Session.configure(badge=ALLOW)
    session = Session()

    def test_add(self):
        session = self.Session()
        with session.switch_badge(10):
            obj = InsertData(data="Insert")
            session.add(obj)
            session.commit()
            assert obj.owner == 10

        with session.switch_badge():
            obj = session.query(InsertData).filter(InsertData.owner == 10).one()
            obj.data = "ALLOW Update"
            session.commit()
            assert obj.data == "ALLOW Update"
            assert obj.owner == 10

        with session.switch_badge(10):
            obj = session.query(InsertData).filter(InsertData.owner == 10).one()
            obj.data = "Owner Update"
            session.commit()
            assert obj.data == "Owner Update"

        with session.switch_badge(20):
            obj.data = "Non-owner Update"
            session.add(obj)
            session.commit()
            assert obj.data == "Non-owner Update"
            assert obj.owner == 10


def test_disallow_baked_queries():
    engine = create_engine("sqlite:///:memory:")#, echo=True)
    User.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)

    session = Session()

    with pytest.raises(AuthException):
        session.enable_baked_queries = True
        session.query(User).all()
