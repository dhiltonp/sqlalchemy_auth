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
    def add_auth_filters(query, user):
        return query.filter_by(owner=user)

    def blocked_read_attributes(self, user):
        return self.blocked_write_attributes(user)

    def blocked_write_attributes(self, user):
        if self.owner != user:
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


Session.configure(user=sqlalchemy_auth.ALLOW)
session = Session()
all_data = session.query(Data).all()
print(len(all_data))

with session.su(2):
    print(len(session.query(Data).all()))
