"""
Dry software run that emulates a target of another scheme
"""

from threading import Thread
from .. import get_scheme
from ..core.transmission import AbstractScheme
from ..core.transmission.abstract import AbstractClient, AbstractServer


class Emulate(AbstractScheme):
    title = "Emulator"
    description = "Emulates a target"
    client_args_help = ("SCHEME",)
    server_args_help = ("SCHEME",)

    @classmethod
    def new_client(cls, *args, **xargs):
        """ Create a server and return a client attached to it """
        server = cls.new_server(*args)
        return server.new_attached_client(**xargs)

    @classmethod
    def new_server(cls, *args, **xargs):
        return cls.new_dummyserver(*args, **xargs)

    @classmethod
    def new_dummyserver(cls, scheme, *args, **xargs):
        return get_scheme(scheme).new_dummyserver(*args, **xargs)


class DummyClientMixin:
    """ This client skips connection related methods """

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._server.bind(send = self._newthread(self.on_receive_raw_data))
        self.bind(send = self._newthread(self._server.on_receive_raw_data))

    def _newthread(self, func):
        # send() shall not block for avoiding deadlocks
        return lambda *args, **kwargs: \
            Thread(target=func, args=args, kwargs=kwargs, name="transmission", daemon=True).start()

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


class DummyEmulate(Emulate):
    """ Emulator without network connection. Only internal variables are being used. """
    title = "Plain Emulator"
    description = "Emulator that skips network"

    @classmethod
    def _get_dummy_scheme(cls, scheme):
        Scheme = get_scheme(scheme)
        class DummyScheme(Scheme):
            """ Server/client without a socket """
            Client = type("Client", (DummyClientMixin, Scheme, AbstractClient), {})
            Server = type("Server", (Scheme, AbstractServer), {})
        return DummyScheme

    @classmethod
    def new_client(cls, *args, **xargs):
        client = super().new_client(*args, **xargs)
        client.uri = f"{cls.scheme_id}:{client.scheme_id}"
        return client

    @classmethod
    def new_dummyserver(cls, scheme, *args, **xargs):
        return cls._get_dummy_scheme(scheme).new_dummyserver(*args, **xargs)

