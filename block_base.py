from sqlalchemy_auth import AuthBase, ALLOW, AuthException


class BlockBase(AuthBase):
    """
    BlockBase provides mechanisms for attribute blocking.

    To block access, return blocked attributes in your own
    _blocked_read_attributes or _blocked_write_attributes.
    """

    def _blocked_read_attributes(self, badge):
        """
        Override _blocked_read_attributes to just block read attributes.

        Only called if badge != ALLOW.
        """
        return set()

    def _blocked_write_attributes(self, badge):
        """
        Override _blocked_write_attributes to just block write attributes.
        Defaults to _blocked_read_attributes.

        Only called if badge != ALLOW.
        """
        return self._blocked_read_attributes(badge)

    def get_blocked_read_attributes(self):
        if self._session.badge is ALLOW:
            return set()
        return set(self._blocked_read_attributes(self._session.badge))

    def get_blocked_write_attributes(self):
        if self._session.badge is ALLOW:
            return set()
        return set(self._blocked_write_attributes(self._session.badge))

    def get_read_attributes(self):
        attrs = {v for v in vars(self) if not v.startswith("_")}
        return attrs - self.get_blocked_read_attributes()

    def get_write_attributes(self):
        attrs = {v for v in vars(self) if not v.startswith("_")}
        return attrs - self.get_blocked_write_attributes()

    # make _session exist at all times.
    #  This matters because sqlalchemy does some magic before __init__ is called.
    # This simplifies the logic in __getattribute__
    class _session:
        badge = ALLOW
    _checking_authorization = False

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
            raise AuthException(f"Read from '{name}' blocked for {self._session.badge} on {self}: {blocked}")
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        blocked = self.get_blocked_write_attributes()
        if name in blocked:
            raise AuthException(f"Write to '{name}' blocked for {self._session.badge} on {self}: {blocked}")
        return super().__setattr__(name, value)
