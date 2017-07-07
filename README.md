# Overview

sqlalchemy_auth provides authorization mechanisms for SQLAlchemy DB access.

It is designed for easy integration into existing projects, allowing a project
to centralize authorization logic over time. It is also easy to bypass when
necessary.

1. All mapped classes can add implicit filters (added when `session.query()`
 is run against the database).
2. All instances of mapped classes can selectively block attribute access.

Your defined methods are passed an `effective_user` parameter when
executed, unless set to `ALLOW`, which bypasses all authorization mechanisms,
or `DENY`, which blocks all access.

`effective_user` can be any type and is automatically set for queries and
mapped class instances on their creation.

# Getting Started

### Session Setup

Create a Session class using the AuthSession and AuthQuery classes:

```python
Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery)
```

To activate filtering:

```python
Session.configure(effective_user=current_user)
session = Session()
```

By default `effective_user` is set to `ALLOW`, so filtering/blocking will not be in effect.

### Implicit Filters

To add implicit filters, define `add_auth_filters`:

```python
class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    @staticmethod
    def add_auth_filters(query, effective_user):
        return query.filter_by(owner=effective_user.id)
```

### Attribute Blocking

For attribute-level blocking, inherit from the AuthBase class (you can also use
mixins instead of `declarative_base(cls=AuthBase)`):

```python
Base = declarative_base(cls=AuthBase)

class AttributeCheck(Base):
    __tablename__ = "attributecheck"

    id = Column(Integer, primary_key=True)
    owner = Column(String)
    data = Column(String)
    secret = Column(String)

    def _blocked_read_attributes(self, effective_user):
        return ["secret"]

    def _blocked_write_attributes(self, effective_user):
        return ["id", "owner"]
```

Four convenience methods are defined:
`get_read_attributes()`, `get_blocked_read_attributes()` and
`get_write_attributes()`, `get_blocked_write_attributes()`. Only public
attributes are returned.

Attribute blocking is only effective for instances of the mapped class.

# Gotchas

### Filtering at Instantiation

`effective_user` is automatically set for queries and objects at their _instantiation_,
based on the value of their parent. For example:

```python
Session.configure(effective_user=ALLOW)
session = Session()
query = session.query(Data)

Session.configure(effective_user=user)
session = Session()

results = query.all()
```

In this example, `results` will not be filtered despite session's `effective_user` being
set, as `effective_user` was `ALLOW` at `query`'s creation. `effective_user` will also be
set to `ALLOW` for all returned objects, bypassing all filtering/blocking.

Technically, assigning `authClassInstance._effective_user` will update filtering on the fly,
but at this time I view it as a protected variable.

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
