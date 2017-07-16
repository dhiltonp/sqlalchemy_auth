# Overview

sqlalchemy_auth provides authorization mechanisms for SQLAlchemy DB access.

It is easy to use, and easy to bypass. 

1. You set and receive a `user` parameter on a session.
2. All mapped classes can add implicit query filters.
3. All mapped classes can selectively block attribute access.

`user` is shared between all queries and mapped class instances within a session.

# Getting Started

### Session

Create a session using the AuthSession and AuthQuery classes:

```python
Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery, user=DENY)
session = Session()
```

By default `user` is set to `ALLOW`, bypassing all filtering/blocking. Change `user`
to activate filtering/blocking:

```python
session.su(user)
```

Temporarily change `user`:

```python
with session.su(ALLOW):
    ...
```

### Filters

To add filters, define `add_auth_filters`:

```python
class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    @staticmethod
    def add_auth_filters(query, user):
        return query.filter_by(owner=user.id)
```

### Attribute Blocking

To block attributes, inherit from the AuthBase class (you can also use
mixins instead of `declarative_base(cls=AuthBase)`):

```python
Base = declarative_base(cls=AuthBase)

class AttributeCheck(Base):
    __tablename__ = "attributecheck"

    id = Column(Integer, primary_key=True)
    owner = Column(String)
    data = Column(String)
    secret = Column(String)

    def _blocked_read_attributes(self, user):
        return ["secret"]

    def _blocked_write_attributes(self, user):
        return ["id", "owner"]
```

Four convenience methods are defined:
`get_read_attributes()`, `get_blocked_read_attributes()` and
`get_write_attributes()`, `get_blocked_write_attributes()`. Only public
attributes are returned.

Attribute blocking is only effective for instances of the mapped class.

# Gotchas

### One User per Session/Query/Objects Group

Only one user exists between a session, its queries and returned objects. For example:

```python
session.su(ALLOW)
query = session.query(Data)
unfiltered = query.all()

session.su(user)
filtered = query.all()
```

In this example, `unfiltered` will contain all results, but the same query later
returns `filtered` results.

### Attribute Blocking Limitations

Attribute blocking relies on the object being an instance of the class with blocks.
In the following example, `add_auth_filters` is applied, but blocks are not:

```python
obj = session.query(Class.attr, Class.blocked_attr).first()
obj.blocked_attr = "foo"
```

Similarly, `update` bypasses attribute blocks:

```python
query = session.query(Class.blocked).update({Class.blocked: "unchecked write"})
```

--------------------------

See sqlalchemy_auth_test.py for full examples.
