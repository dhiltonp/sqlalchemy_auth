#!/usr/bin/python

import sqlalchemy_auth
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base(cls=sqlalchemy_auth.AuthBase)


def create_db():
    engine = create_engine('sqlite:///:memory:')#, echo=True)

    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, class_=sqlalchemy_auth.AuthSession, query_cls=sqlalchemy_auth.AuthQuery)
    Session.configure(effective_user=None)

    return Session


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String)


class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer, ForeignKey(User.id))
    data = Column(String)

    @staticmethod
    def add_auth_filters(query, effective_user):
        return query.filter_by(owner=effective_user)

    def blocked_read_attributes(self, effective_user):
        return self.blocked_write_attributes(effective_user)

    def blocked_write_attributes(self, effective_user):
        if self.owner != effective_user:
            return ["data"]
        return []

def add_data(session):
    session.add_all([
        User(username="alice"),
        User(username="bob"),
        User(username="charles")
    ])

    session.add_all([
        Data(owner=1, data="A"),

        Data(owner=2, data="B"),
        Data(owner=2, data="B"),

        Data(owner=3, data="A"),
        Data(owner=3, data="B"),
        Data(owner=3, data="C"),
        Data(owner=3, data="D")])

    session.commit()

Session = create_db()
add_data(Session())


Session.configure(effective_user=None)
session = Session()
all_data = session.query(Data).all()
print(len(all_data))

all_data[0]._effective_user = 2
print(all_data[0].data)
