#!/usr/bin/python
import collections
from enum import Enum

import sqlalchemy.orm.attributes


class _Access(Enum):
    Allow = "Allow"
    Deny = "Deny"

ALLOW = _Access.Allow
DENY = _Access.Deny


class _Settings:
    """
    _Settings allows an AuthSession to share the `user` with other classes
    so that if it is changed here, it changes everywhere.
    """
    def __init__(self):
        self.user = ALLOW


class AuthException(Exception):
    pass


class AuthSession(sqlalchemy.orm.session.Session):
    """
    AuthSession constructs all queries with the set user.
    """
    def __init__(self, user=ALLOW, *args, **kwargs):
        self._auth_settings = _Settings()
        self._auth_settings.user = user
        super().__init__(*args, **kwargs)

    def su(self, user=ALLOW):
        self._auth_settings.user = user

    def query(self, *args, **kwargs):
        return super().query(*args, auth_settings=self._auth_settings, **kwargs)


class _AuthQuery(sqlalchemy.orm.query.Query):
    """
    AuthQuery provides a mechanism for returned objects to know which user looked them up.
    """

    _Entity = collections.namedtuple('_Entity', ['class_', 'mapper'])

    def __init__(self, *args, auth_settings=DENY, **kwargs):
        self._auth_settings = auth_settings
        super().__init__(*args, **kwargs)

    def _compile_context(self, labels=True):
        filtered = self._add_auth_filters()
        return super(self.__class__, filtered)._compile_context(labels)

    def _execute_and_instances(self, querycontext):
        instances_generator = super()._execute_and_instances(querycontext)
        for row in instances_generator:
            # all queries come through here - including ones that don't return model instances
            #  (count, for example).
            # Assuming it's an uncommon occurrence, we'll try/accept (test this later)
            try:
                row._auth_settings = self._auth_settings
            except AttributeError:
                pass
            yield row

    def update(self, *args, **kwargs):
        # TODO: assert that protected attributes aren't modified?
        filtered = self._add_auth_filters()
        return super(self.__class__, filtered).update(*args, **kwargs)

    def delete(self, *args, **kwargs):
        filtered = self._add_auth_filters()
        return super(self.__class__, filtered).delete(*args, **kwargs)

    def _add_auth_filters(self):
        # NOTICE: This is in the display path (via __str__?); if you are debugging
        #  with pycharm and hit a breakpoint, this code will silently execute,
        #  potentially causing filters to be added twice. This should have no affect
        #  on the results.
        if self._auth_settings.user is DENY:
            raise AuthException("Access is denied")

        filtered = self
        original_select_from_entity = filtered._select_from_entity
        if filtered._auth_settings.user is not ALLOW:
            # add_auth_filters
            for entity in self._lookup_entities():
                # setting _select_from_entity allows query(id=...) to work inside of
                #  add_auth_filters when doing a join
                filtered._select_from_entity = entity.mapper
                filtered = entity.class_.add_auth_filters(filtered, filtered._auth_settings.user)

        filtered._select_from_entity = original_select_from_entity
        return filtered

    def _lookup_entities(self):
        """returns an _Entity list without duplicate entries, for entities that belong in the
         object Model (for example: Class inheriting from Base or Class.attribute)"""
        from sqlalchemy.ext.declarative.api import DeclarativeMeta
        found_entities = {}
        entities = []

        if len(self.column_descriptions) != len(self._entities):
            # gonna have to figure out this case; raise
            raise Exception("mismatched dict lengths; investigate")

        # find entities, eliminate duplicates
        for entity in self._entities:
            # already processed?
            if entity in found_entities:
                continue

            # add new entity
            class_ = [col['entity'] for col in self.column_descriptions if col['expr'] == entity.expr][0]
            if isinstance(class_, DeclarativeMeta):
                entities.append(self._Entity(class_=class_, mapper=entity.mapper))
            else:
                # count, uses raw integers and have no base class
                continue
                # gonna have to figure out this case; raise
                raise Exception("unable to determine type")

            found_entities[entity] = True

        return entities


class _AuthBase:
    # make _auth_settings exist at all times.
    #  This matters because sqlalchemy does some magic before __init__ is called.
    # We set it to simplify the logic in __getattribute__
    _auth_settings = _Settings()
    _checking_authorization = False

    def get_blocked_read_attributes(self):
        if self._auth_settings.user is not ALLOW:
            return self._blocked_read_attributes(self._auth_settings.user)
        return []

    def get_blocked_write_attributes(self):
        if self._auth_settings.user is not ALLOW:
            return self._blocked_write_attributes(self._auth_settings.user)
        return []

    def get_read_attributes(self):
        attrs = [v for v in vars(self) if not v.startswith("_")]
        return set(attrs) - set(self.get_blocked_read_attributes())

    def get_write_attributes(self):
        attrs = [v for v in vars(self) if not v.startswith("_")]
        return set(attrs) - set(self.get_blocked_write_attributes())

    def __getattribute__(self, name):
        # __getattribute__ is called before __init__ by a SQLAlchemy decorator.

        # bypass our check if we're recursive
        # this allows _blocked_read_attributes to use self.*
        if super().__getattribute__("_checking_authorization"):
            return super().__getattribute__(name)

        # look up blocked attributes
        super().__setattr__("_checking_authorization", True)
        blocked = self.get_blocked_read_attributes()
        super().__setattr__("_checking_authorization", False)

        # take action
        if name in blocked:
            raise AuthException('{} may not access {} on {}'.format(self._auth_settings.user, name, self.__class__))
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if name in self.get_blocked_write_attributes():
            raise AuthException('{} may not access {} on {}'.format(self._auth_settings.user, name, self.__class__))
        return super().__setattr__(name, value)


class AuthBase(_AuthBase):
    """
    Provide authorization behavior (default: allow everything).
    To block access, return blocked attributes in your own 
    _blocked_read_attributes or _blocked_write_attributes.

    Subclass using mixins or by passing the class into declarative_base:

        class Foo(Base, AuthBase):

    or 

        Base = declarative_base(cls=sqlalchemy_auth.AuthBase)    
    """

    @staticmethod
    def add_auth_filters(query, user):
        """
        Override this to add implicit filters to a query, before any additional
        filters are added.
        """
        return query

    def _blocked_read_attributes(self, user):
        """
        Override this method to block read access to attributes, but use 
        the get_* methods for access.

        Only called if user != ALLOW.
        """
        return []

    def _blocked_write_attributes(self, user):
        """
        Override this method to block write access to attributes, but use 
        the get_* methods for access.

        Only called if user != ALLOW.
        """
        return []
