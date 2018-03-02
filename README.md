# Overview

sqlalchemy_auth provides authorization mechanisms for SQLAlchemy DB access.

It is easy to use, and easy to bypass when needed.

1. You set a `badge` on a session, which is passed to various handlers.
2. All mapped classes can add implicit filters on queries and implicit data on inserts.
3. All mapped classes can selectively block attribute access.

Your `badge` is shared between all queries and mapped class instances within a session.


# Getting Started

### Session

Create a session using the AuthSession and AuthQuery classes:

```python
Session = sessionmaker(bind=engine, class_=AuthSession, query_cls=AuthQuery, badge=DENY)
session = Session()
```

By default you don't need no stinking `badge`. It is set to `ALLOW`, bypassing all auth
mechanisms (the default is overridden above). Change `badge` from `ALLOW` to enable
authorization:

```python
session.badge=badge
```

Temporarily switch `badge`:

```python
with session.switch_badge(badge):
    ...
```

`badge` can be anything (the current user, their role, etc.), and will be passed in to 
`add_auth_filters` and `add_auth_insert_data` (unless it's `ALLOW` or `DENY`).


### Filters

To add filters, define `add_auth_filters`:

```python
class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    @classmethod
    def add_auth_filters(cls, query, badge):
        return query.filter_by(owner=badge.user_id)
```


### Inserts

To add data on insert, define `add_auth_insert_data`:

```python
class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True)
    owner = Column(Integer)
    data = Column(String)

    def add_auth_insert_data(self, badge):
        self.owner = badge.user_id
```


### Default Filters and Inserts

If your `Base` inherits from `AuthBase`, you will inherit no-op `add_auth_filters` 
and `add_auth_insert_data` methods.


### Attribute Blocking

To block attributes, inherit from the `BlockBase` class (you can also use
mixins instead of `declarative_base(cls=BlockBase)`):

```python
Base = declarative_base(cls=BlockBase)

class AttributeCheck(Base):
    __tablename__ = "attributecheck"

    id = Column(Integer, primary_key=True)
    owner = Column(String)
    data = Column(String)
    secret = Column(String)

    def _blocked_read_attributes(self, badge):
        if self.owner == badge.user_id:
            return []
        return ["secret"]

    def _blocked_write_attributes(self, badge):
        blocked = ["id", "owner"]
        if self.owner != badge.user_id:
            blocked.append("data")
        return blocked
```

These methods are only called if badge != `ALLOW` and you are within a transaction.
By default, `_blocked_write_attributes` calls `_blocked_read_attributes`.

Four convenience methods are defined:

`readable_attrs()`, `read_blocked_attrs()`, `writable_attrs()` and `write_blocked_attrs()`

Here are some examples of attribute blocking:

```python
a = session.query(AttributeCheck).one()

if "secret" in a.readable_attrs():
    display_secret(a)

try:
    a.data = "value"
except AuthException:
    raise
```

Attribute blocking is only effective for instances of the mapped class.


# Gotchas

### One Badge per Session/Query/Objects Group

Only one badge exists between a session, its queries and returned objects.
For example:

```python
session.badge = ALLOW
query = session.query(Data)
unfiltered = query.all()

session.badge = badge
filtered = query.all()
```

In this example, `unfiltered` will contain all Data objects, but the same 
query later would return a `filtered` subset.


### Mixed Permissions of Objects

Relationships may be loaded with a different badge from their parent/child.

```python
session.badge = badge
shared_data = session.query(Data).first()

session.badge = ALLOW
shared_data.owners

session.badge = badge
shared_data.owners
```

In the above example the `owners` relationship is loaded without filtering.
Changing `badge` does not invalidate or reload `owners`; it will persist and
not be filtered.

`session.expunge_all()` will invalidate all objects, so all objects will be
re-filtered. `session.expunge(shared_data)` would also work above.


### Scoped Session Usage

To support `scoped_session.query` style syntax with `badge` and `switch_badge`, you must run
`instrument_scoped_session` on the value returned by `sqlalchemy.orm.scoped_session()`.

If you do not, setting `badge` will have no effect and calling `switch_badge` will raise
`AttributeError: 'scoped_session' object has no attribute 'switch_badge'`.


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

### BakedQueries not Cached

BakedQuery will correctly execute, but will not be baked/cached.

sqlalchemy_auth hooks sqlalchemy's compilation, which only occurs once per
BakedQuery. The query would be baked with one badge, forever.

This would include relationship queries.


--------------------------

See auth_query_test.py for end-to-end examples.
