from .core import config, AbstractScheme, AbstractServer, AbstractClient, features
from .info import *
from .core.transmission.scheme_inventory import schemes, get_scheme, get_schemes, register_scheme


class URI:

    def __init__(self, uri):
        uri = uri.replace("://", ":")
        split = min([self._find(uri, x) for x in "?/#"])
        uri, path = uri[:split], uri[split:]
        split = self._find(path, "?")
        path, query = path[:split], path[split:]
        self.uri = [uri.split(":") if uri else uri, path, query]

    scheme = property(lambda self: self.uri[0][0])
    args = property(lambda self: self.uri[0][1:])
    path = property(lambda self: self.uri[1])
    query = property(lambda self: self.uri[2])
    tail = property(lambda self: "".join(self.uri[1:]))

    def _find(self, s, substr):
        idx = s.find(substr)
        return idx if idx >= 0 else len(s)

    def update(self, uri):
        other = URI(uri)
        copy = False
        for i in range(len(self.uri)):
            if other.uri[i]: copy = True
            if copy: self.uri[i] = other.uri[i]
        return self


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
    uri_ = URI(config.get("Target", "uri"))
    if uri: uri_.update(uri)
    Scheme = getattr(get_scheme(uri_.scheme), f"new_{role}")
    target = Scheme(*uri_.args, *args, **xargs)
    if uri_.tail:
        with target: target.handle_uri_path(uri_)
    return target

