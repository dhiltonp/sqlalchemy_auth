from sqlalchemy.orm.session import ACTIVE

from sqlalchemy_auth import AuthBase, ALLOW, AuthException


def _authcheck(func):
    def wrapper(self, *args, **kwargs):
        self._checking_authorization = True
        if self._bypass_block():
            result = set()
        else:
            result = func(self, *args, **kwargs)
        self._checking_authorization = False

        return result
    return wrapper


class BlockBase(AuthBase):
    """
    BlockBase provides mechanisms for attribute blocking.

    To block both read and write access, return blocked attributes in
    your own _blocked_read_attributes. _blocked_write_attributes calls
    it out of the box.

    To additionally block write access, implement _blocked_write_attributes.
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

    @_authcheck
    def read_blocked_attrs(self):
        """
        :return: set of attrs that are not readable.
        """
        return set(self._blocked_read_attributes(self._session.badge))

    @_authcheck
    def write_blocked_attrs(self):
        """
        :return: set of attrs that are not writable.
        """
        return set(self._blocked_write_attributes(self._session.badge))

    def readable_attrs(self):
        """
        :return: set of attrs that are readable.
        """
        attrs = {v for v in vars(self) if not v.startswith("_")}
        return attrs - self.read_blocked_attrs()

    def writable_attrs(self):
        """
        :return: set of attrs that are writable.
        """
        attrs = {v for v in vars(self) if not v.startswith("_")}
        return attrs - self.write_blocked_attrs()

    # make _session exist at all times.
    #  This matters because sqlalchemy does some magic before __init__ is called.
    # This simplifies the logic in __getattribute__
    class _session:
        badge = ALLOW

    # _checking_authorization is always readable/writable
    _checking_authorization = False

    def __getattribute__(self, name):
        # bypass blocking if we're checking attributes
        # this allows _blocked_read_attributes to use self.*
        if super().__getattribute__("_checking_authorization") or name == "read_blocked_attrs":
            return super().__getattribute__(name)

        blocked = self.read_blocked_attrs()
        if name in blocked:
            with self._session.switch_badge():  # so self can be used in the exception message
                raise AuthException("Read from '{name}' blocked for {badge} on {self}: {blocked}".
                                    format(name=name, badge=self._session.badge, self=self, blocked=blocked))
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if name == "_checking_authorization":
            return super().__setattr__(name, value)

        blocked = self.write_blocked_attrs()
        if name in blocked:
            with self._session.switch_badge():  # so self can be used in the exception message
                raise AuthException("Write to '{name}' blocked for {badge} on {self}: {blocked}".
                                    format(name=name, badge=self._session.badge, self=self, blocked=blocked))
        return super().__setattr__(name, value)

    def _bypass_block(self):
        return not hasattr(self._session, "transaction") \
            or self._session.transaction._state is not ACTIVE \
            or self._session.badge is ALLOW
