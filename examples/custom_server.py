"""
This shows how to share values from an external entity with clients in a client-server architecture.

Run server:
    examples$ python3 -m hificon.server -t custom_server.MyScheme://127.0.0.1:1234:40
Run client:
    examples$ python3 -m hificon.hifish -t custom_server.MyScheme://127.0.0.1:1234
    The value $counter shall always be synchronised with the server.
"""

import time
from threading import Thread, Lock
from hificon.core import shared_vars, SocketServer, SocketScheme
from hificon import Target, register_scheme


class ExternalCounter:
    """ This just increases numbers independently. This is only being run on the server. """
    value = 0
    lock = Lock()

    def __init__(self, var):
        self.var = var
        Thread(target=self.count, daemon=True).start()

    def count(self):
        while True:
            self.set((self.value+1)%10)
            time.sleep(5)

    def set(self, value):
        if value < 50:
            with self.lock:
                self.value = value
                self.var.set(self.value) # sync clients


class MyServer(SocketServer):
    """ Adds a custom value START_COUNT to init and changes the URI to
    SCHEME://IP:PORT:START_COUNT
    """
    init_args_help = ("//LISTEN_IP", "LISTEN_PORT", "START_COUNT")
    
    def __init__(self, ip="127.0.0.1", port=0, start=None, *args, **xargs):
        super().__init__(ip, port, *args, **xargs)
        if start: self.shared_vars.counter.external_counter.set(int(start))


class MyScheme(SocketScheme):
    """ must have the reference to MyServer """
    description = "My custom scheme"
    Server = MyServer


@MyScheme.shared_var
class CounterShared(shared_vars.IntVar):
    """ connects ExternalCounter with the server and clients """
    key = "counter"
    min = 0
    max = 50
    call = "get counter"
    
    def serialize(self, value): return "set counter %d"%value
    def unserialize(self, data): return int(data.rsplit(" ",1)[1])
    def matches(self, data): return data.startswith("set counter")
    def init_on_server(self): self.external_counter = ExternalCounter(self)
    def set_on_server(self, value): self.external_counter.set(value)
    def poll_on_server(self): self.set(self.external_counter.value)


if __name__ == "__main__":
    with MyScheme.new_server(): input("Running. Press ENTER to quit")

