import importlib
import math
from decimal import Decimal
from .core import ProtocolType, config, AbstractProtocol, AbstractServer, AbstractClient, features
from .info import *


def Amp_cls(protocol=None, cls="Amp"):
    """ returns amp instance from @protocol module. Read @protocol from config if None """
    protocol = protocol or config.get("Connection","protocol")
    try:
        module = importlib.import_module(protocol, "%s.protocol"%__name__)
    except ImportError:
        raise ValueError("Amp protocol `%s` not found."%protocol)
    Protocol = getattr(module, cls)
    assert(issubclass(Protocol, ProtocolType))
    return Protocol


class _ProtocolInheritance(type):
    """ Adds first parameter @protocol (str) to __init__ and will inherit a class cls from
    (Protocol, cls._parent(Protocol)) where @protocol points at Protocol module.
    @target is a URI in the scheme protocol_module:arg_1:...:arg_n, e.g. .denon://127.0.0.1:23
    Read @target from config if None """

    def __call__(cls, target=None, *args, **xargs):
        target = target.split(":") if target else [None]
        Protocol = Amp_cls(protocol=target.pop(0))
        Complete = type(cls.__name__, (cls, Protocol, cls._parent(Protocol)), {})
        return super(_ProtocolInheritance, Complete).__call__(*target, *args, **xargs)


class Client(metaclass=_ProtocolInheritance):
    _parent = staticmethod(lambda Protocol: Protocol.Client)


class Server(metaclass=_ProtocolInheritance):
    _parent = staticmethod(lambda Protocol: Protocol.Server)


class DummyServer(Server):
    """ Server class that fills feature values with some values """

    default_values = dict(
        name = "Dummy X7800H",
    )

    def poll_feature(self, f, *args, **xargs):
        if f.isset(): val = f.get()
        elif f.key in self.default_values: val = self.default_values[f.key]
        elif getattr(f, "default_value", None): val = f.default_value
        elif isinstance(f, features.IntFeature): val = math.ceil((f.max+f.min)/2)
        elif isinstance(f, features.DecimalFeature): val = Decimal(f.max+f.min)/2
        elif isinstance(f, features.BoolFeature): val = False
        elif isinstance(f, features.SelectFeature): val = f.options[0] if f.options else "?"
        else: raise TypeError("Feature type %s not known."%f)
        f.store(val)


class LocalDummyServer(DummyServer):
    """ DummyServer that acts only inside the process like a variable """
    _parent = staticmethod(lambda Protocol: AbstractServer)


class _ConnectLocalDummyServer(_ProtocolInheritance):

    def __call__(cls, target=None, *args, **xargs):
        client = super().__call__(target, *args, **xargs)
        server = LocalDummyServer(target)
        client.bind(send = lambda data: server.on_receive_raw_data(data))
        server.bind(send = lambda data: client.on_receive_raw_data(data))
        return client


class DummyClient(metaclass=_ConnectLocalDummyServer):
    """ This client class connects to an internal server instance """
    host = "emulator"
    _parent = staticmethod(lambda Protocol: AbstractClient)

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.port = None

    def connect(self):
        super().connect()
        self.on_connect()

    def disconnect(self):
        super().disconnect()
        self.on_disconnected()

    def mainloop(self):
        if not self.connected: self.connect()
    
    def send(self, data):
        super().send(data)
        if not self.connected: raise BrokenPipeError("Not connected")


Amp = Client

