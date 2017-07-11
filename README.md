# Overview

sqlalchemy_auth provides authorization mechanisms for SQLAlchemy DB access.

It is easy to use, and easy to bypass. 

1. You set and receive a `user` parameter. 
2. All mapped classes can add implicit filters.
3. All mapped classes can selectively block attribute access.

# Getting Started

### Session Setup

Create a Session class using the AuthSession and AuthQuery classes:

```python
Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
```

By default `user` is set to `ALLOW`, bypassing all filtering/blocking.

Activate filtering/blocking:

```python
Session.configure(user=current_user)
session = Session()
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

For attribute blocking, inherit from the AuthBase class (you can also use
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

### Temporarily Changing User


```python
Session.configure(user=user)
session = Session()
filtered_query1 = session.query(Data)
overridden_query = session.query(Data, user=ALLOW)
filtered_query2 = session.query(Data)
```

# Gotchas

### Filtering at Instantiation

`user` is automatically set for queries and objects at their _instantiation_,
based on the value of their parent. For example:

```python
Session.configure(user=ALLOW)
session = Session()
query = session.query(Data)

Session.configure(user=user)
session = Session()

results = query.all()
```

In this example, `results` will not be filtered despite session's `user` being
set, as `user` was `ALLOW` at `query`'s creation.

### Attribute Blocking Limitations

Attribute blocking relies on the object being an instance of the class with blocks.
In the following example, `add_auth_filters` is applied, but blocks are not:

```python
obj = session.query(Class.attr, Class.blocked_attr).first()
obj.blocked_attr = "foo"
```

Similarly, `update` bypasses attribute blocks:

```python
query = session.query(Class.blocked).update({Class.blocked: "unchecked overwrite"})
```

--------------------------

See sqlalchemy_auth_test.py for full examples.
