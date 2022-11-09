from .emulate import Emulate
from .. import get_scheme


class ClientRepeaterMixin:
    _client = None
    
    def __init__(self, target, *args, **xargs):
        self._client = target
        self._client.preload_features = self._client.features.keys()
        self._client.bind(on_receive_raw_data = lambda data:self.send(data))
        super().__init__(*args, **xargs)
    
    def new_attached_client(self, *args, **xargs):
        return self._client

    def enter(self):
        super().enter()
        self._client.start()
        self.uri = f"{self.scheme_id}:{self._client.uri}"

    def exit(self):
        super().exit()
        self._client.stop()

    def on_receive_raw_data(self, data):
        try: self._client.send(data)
        except ConnectionError as e: print(repr(e))


class Repeat(Emulate):
    title = "Repeater"
    description = "A server that connects to another server and repeats the data"
    server_args_help = ("CLIENT_URI",)
    client_args_help = None

    @classmethod
    def new_server(cls, scheme, *args, **xargs):
        target = get_scheme(scheme).new_client(*args, connect=False)
        Server = type("Repeater", (ClientRepeaterMixin, target.Server), {})
        return cls._new_target(Server)(target, **xargs)

