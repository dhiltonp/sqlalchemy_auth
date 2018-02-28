from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import Query, Mapper
from sqlalchemy.orm.query import _QueryEntity
from sqlalchemy.orm.util import AliasedInsp, AliasedClass

from sqlalchemy_auth import AuthException, BlockBase, ALLOW, DENY


class AuthQuery(Query):
    """
    AuthQuery modifies query generation to add implicit filters as needed.
    It also sets _session on returned objects.
    """
    def __init__(self, entities, session=None):
        super().__init__(entities=entities, session=session)
        self._auth_from_entities = self._update_entity_set(entities, set())
        self._auth_join_entities = set()

    def _compile_context(self, labels=True):
        if getattr(self, "_compile_context_guard", False):
            raise RecursionError("Preview not supported while compiling query")
        self.session._assert_no_baked_queries()

        self._compile_context_guard = True
        filtered = self._add_auth_filters()
        del filtered._compile_context_guard
        self._compile_context_guard = False

        return super(AuthQuery, filtered)._compile_context(labels)

    def _execute_and_instances(self, querycontext):
        # Required for BlockBase
        instances_generator = super()._execute_and_instances(querycontext)
        for row in instances_generator:
            if isinstance(row, BlockBase):
                row._session = self.session
            yield row

    @staticmethod
    def _get_entities(objects):
        """
        copy Query._set_entities() behaviour providing dummy instance for
        entities to accumulate on via entity_wrapper side effect
        """
        class dummy:
            _entities = []
            _primary_entity = None
        for obj in objects:
            _QueryEntity(dummy, obj)
        return dummy._entities

    def _update_entity_set(self, objects, entity_set):
        entity_set = entity_set.copy()
        for obj in self._get_entities(objects):
            for entity in obj.entities:
                if isinstance(entity, Mapper):
                    entity_set.add(entity.class_)
                elif isinstance(entity, AliasedInsp):
                   entity_set.add(entity.entity)
                elif isinstance(entity, DeclarativeMeta) or isinstance(entity, AliasedClass):
                    entity_set.add(entity)
                else:
                    raise AuthException("Unknown entity type:", entity)
        return entity_set

    def _join_to_left(self, l_info, left, right, onclause, outerjoin, full):
        super()._join_to_left(l_info, left, right, onclause, outerjoin, full)
        self._auth_join_entities = self._update_entity_set([right], self._auth_join_entities)

    def _set_select_from(self, obj, set_base_alias):
        super()._set_select_from(obj, set_base_alias)
        self._auth_from_entities = self._update_entity_set(obj, self._auth_from_entities)

    def update(self, *args, **kwargs):
        # TODO: assert that protected attributes aren't modified?
        filtered = self._add_auth_filters()
        return super(AuthQuery, filtered).update(*args, **kwargs)

    def delete(self, *args, **kwargs):
        filtered = self._add_auth_filters()
        return super(AuthQuery, filtered).delete(*args, **kwargs)

    def _get_filter_entities(self):
        filter_entities = set()
        if self._orm_only_from_obj_alias:
            filter_entities.update(self._auth_from_entities)
            filter_entities.update(self._auth_join_entities)
        return filter_entities

    def _add_auth_filters(self):
        if self.session.badge is DENY:
            raise AuthException("Access is denied")

        try:
            # don't try to add filters if we've been given a text statement to execute.
            self._no_statement_condition("_add_auth_filters")
        except InvalidRequestError:
            return self

        filtered = self.enable_assertions(False)
        if self.session.badge is not ALLOW:
            for class_ in self._get_filter_entities():
                # setting _select_from_entity allows filter_by(id=...) to target class_'s entity inside of
                #  add_auth_filters when doing a join
                filtered._select_from_entity = class_.__mapper__
                filtered = class_.add_auth_filters(filtered, self.session.badge)

        return filtered
