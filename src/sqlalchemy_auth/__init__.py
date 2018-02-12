from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    __version__ = 'unknown'


from .utils import ALLOW, DENY, AuthException
from .auth_base import AuthBase
from .block_base import BlockBase
from .auth_query import AuthQuery
from .auth_session import AuthSession, instrument_scoped_session
