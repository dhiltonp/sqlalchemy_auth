class AuthBase:
    """
    _AuthBase provides default methods for add_auth_filters and add_auth_insert_data.

    Subclass using mixins or by passing the class into declarative_base:

        class Foo(Base, AuthBase):

    or

        Base = declarative_base(cls=AuthBase)
    """
    @classmethod
    def add_auth_filters(cls, query, badge):
        """
        Override this to add implicit filters to a query, before any additional
        filters are added.
        """
        return query

    def add_auth_insert_data(self, badge):
        """
        Override this to assign implicit values to a new object (for example,
        via Session.add(Base()))
        """
        pass
