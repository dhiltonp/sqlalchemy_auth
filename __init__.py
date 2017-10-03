#!/usr/bin/python
from enum import Enum

from sqlalchemy import inspect
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.util import AliasedClass


class _Access(Enum):
    Allow = "Allow"
    Deny = "Deny"


ALLOW = _Access.Allow
DENY = _Access.Deny


class AuthException(Exception):
    pass


class _Settings:
    """
    _Settings allows an AuthSession to share the `user` with other classes
    so that if it is changed here, it changes everywhere.
    """
    def __init__(self):
        self.user = ALLOW


class _UserContext:
    def __init__(self, settings):
        self._settings = settings
        self._user = self._settings.user

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._settings.user = self._user


class AuthSession(Session):
    """
    AuthSession manages user/_auth_settings and passes it to queries.
    """
    def __init__(self, user=ALLOW, *args, **kwargs):
        self._auth_settings = _Settings()
        self._auth_settings.user = user
        super().__init__(*args, **kwargs)

    def su(self, user=ALLOW):
        context = _UserContext(self._auth_settings)
        self._auth_settings.user = user
        return context

    def query(self, *args, **kwargs):
        return super().query(*args, **kwargs)

    def _save_impl(self, state):
        if self._auth_settings.user is DENY:
            raise AuthException("Access is denied")
        if self._auth_settings.user is not ALLOW:
            state.object.add_auth_insert_data(self._auth_settings.user)
        super()._save_impl(state)


class AuthQuery(Query):
    """
    AuthQuery modifies query generation to add implicit filters as needed.
    It also sets user/_auth_settings on returned objects.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auth_from_entities = set()
        self._auth_join_entities = set()

    def _compile_context(self, labels=True):
        if hasattr(self, "_compile_context_guard") and self._compile_context_guard:
            return self._compile_context_retval
        self._compile_context_guard = True
        filtered = self._add_auth_filters()
        self._compile_context_retval = super(AuthQuery, filtered)._compile_context(labels)
        #print(self.statement)

        self._compile_context_guard = False
        return self._compile_context_retval

    def _execute_and_instances(self, querycontext):
        instances_generator = super()._execute_and_instances(querycontext)
        for row in instances_generator:
            # all queries come through here - including ones that don't return model instances
            #  (count, for example).
            # Assuming it's an uncommon occurrence, we'll try/accept (test this later)
            try:
                row._auth_settings = self.session._auth_settings
            except AttributeError:
                pass
            yield row

    def update_entity_set(self, objects, entity_set):
        entity_set = entity_set.copy()
        for obj in objects:
            info = inspect(obj)
            if hasattr(info, "entity") and isinstance(info.entity, (AliasedClass, DeclarativeMeta)):
                entity_set.add(info.entity)
        return entity_set

    def _join(self, keys, outerjoin, full, create_aliases, from_joinpoint):
        val = super()._join(keys, outerjoin, full, create_aliases, from_joinpoint)
        val._auth_join_entities = self.update_entity_set(keys, self._auth_join_entities)
        return val

    def _set_select_from(self, obj, set_base_alias):
        super()._set_select_from(obj, set_base_alias)
        self._auth_from_entities = self.update_entity_set(obj, self._auth_from_entities)

    def update(self, *args, **kwargs):
        # TODO: assert that protected attributes aren't modified?
        filtered = self._add_auth_filters()
        return super(AuthQuery, filtered).update(*args, **kwargs)

    def delete(self, *args, **kwargs):
        filtered = self._add_auth_filters()
        return super(AuthQuery, filtered).delete(*args, **kwargs)

    def _get_filter_entities(self):
        filter_entities = {x['entity'] for x in self.column_descriptions if isinstance(x['entity'], DeclarativeMeta)}
        if self._orm_only_from_obj_alias:
            filter_entities.update(self._auth_from_entities)
            filter_entities.update(self._auth_join_entities)
        return filter_entities

    def _add_auth_filters(self):
        # NOTICE: This is in the display path (via __str__?); if you are debugging
        #  with pycharm and hit a breakpoint, this code will silently execute,
        #  potentially causing filters to be added twice. This should have no affect
        #  on the results.
        if self.session._auth_settings.user is DENY:
            raise AuthException("Access is denied")

        try:
            #pass
            # don't try to add filters if we've been given a text statement to execute.
            self._no_statement_condition("_add_auth_filters")
        except InvalidRequestError:
            return self

        filtered = self.enable_assertions(False)
        if self.session._auth_settings.user is not ALLOW:
            # actually call add_auth_filters
            for class_ in self._get_filter_entities():
                # setting _select_from_entity allows filter_by(id=...) to target class_'s entity inside of
                #  add_auth_filters when doing a join
                filtered._select_from_entity = class_.__mapper__
                filtered = class_.add_auth_filters(filtered, self.session._auth_settings.user)

        return filtered


class _AuthBase:
    """
    _AuthBase provides mechanisms for attribute blocking.
    """
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

    @classmethod
    def add_auth_filters(cls, query, user):
        """
        Override this to add implicit filters to a query, before any additional
        filters are added.
        """
        return query

    def add_auth_insert_data(self, user):
        """
        Override this to assign implicit values to a new object (for example,
        via Session.add(Base()))
        """
        pass

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


def instrument_scoped_session(scoped_session):
    from sqlalchemy.orm.scoping import instrument
    setattr(scoped_session, 'su', instrument('su'))
