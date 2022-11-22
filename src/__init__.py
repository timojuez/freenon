from .core import config, AbstractScheme, AbstractServer, AbstractClient, features
from .info import *
from .core.transmission.scheme_inventory import schemes, get_scheme, get_schemes, register_scheme


def Target(uri=None, *args, role="client", **xargs):
    """
    Returns a scheme instance. The scheme class path must be contained in the URI.
    @uri: URI to connect to. Syntax: scheme_cls:arg_1:...:arg_n. Will be read from config by default.
        Examples:
            denon://192.168.1.15:23
            emulate:denon
            ?volume=20
    @role: Method "new_@role" will be called on the scheme for instantiation. Can be "client", "server" or "dummyserver".
    """
    if uri and "?" in uri: uri, query = uri.split("?",1)
    else: query = None
    if not uri: uri = config.get("Target", "uri").split("?",1)[0]
    uri = uri.split(":")
    Scheme = getattr(get_scheme(uri.pop(0)), f"new_{role}")
    target = Scheme(*uri, *args, **xargs)
    if query:
        with target: target.handle_query(query)
    return target

