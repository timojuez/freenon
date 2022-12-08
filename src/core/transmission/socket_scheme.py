import socket, traceback, sys, time
from threading import Lock
from contextlib import suppress
from datetime import datetime, timedelta
from ..util import socket_tools
from .abstract import AbstractScheme, AbstractClient, AbstractServer


PORT = 23
BUFFER_LENGTH = 1024 # bytes


class _IO(socket_tools.Base):
    _break = b"\r"

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._buf = {}
        self.verbose = self._verbose

    def add_socket(self, sock):
        self._buf[sock] = b""
        super().add_socket(sock)

    def remove_socket(self, sock):
        super().remove_socket(sock)
        del self._buf[sock]

    def update_uri(self):
        super().update_uri(f"//{self.host}", self.port)

    def read(self, data, conn):
        buf = self._buf[conn] + data
        while self._break in buf:
            data_, buf = buf.split(self._break, 1)
            try: decoded = data_.decode()
            except: print(traceback.format_exc())
            else: self.on_receive_raw_data(decoded)
        self._buf[conn] = buf[-BUFFER_LENGTH:]

    def send(self, data):
        super().send(data)
        self.write(self._encode(data))

    def _encode(self, data):
        return (b"%s%s"%(data.encode("ascii"), self._break))

    def schedule(self, *args, **xargs):
        try: return super().schedule(*args, **xargs)
        finally: self.trigger_mainloop()

    def handle_uri_path(self, *args, **xargs):
        super().handle_uri_path(*args, **xargs)
        time.sleep(.2)


class SocketClient(_IO, socket_tools.Client, AbstractClient):
    """
    This class connects to the server via LAN and executes commands
    @host is the server's hostname or IP.
    """
    init_args_help = ("//SERVER_IP", "SERVER_PORT")
    _pulse = "" # this is being sent regularly to keep connection
    _next_pulse = datetime.fromtimestamp(0)

    def __init__(self, host, port=PORT, *args, **xargs):
        if host and host.startswith("//"): host = host[2:]
        super().__init__(host, port, *args, **xargs)
        self._connect_lock = Lock()

    def send(self, cmd):
        if not self.connected: raise BrokenPipeError(f"{self} not connected to {self.uri}.")
        super().send(cmd)

    def connect(self):
        with self._connect_lock:
            if self.connected: return
            try: super().connect(timeout=2)
            except (ConnectionError, socket.timeout, socket.gaierror, socket.herror, OSError) as e:
                raise ConnectionError(e)
            else: self.on_connect()

    def disconnect(self, *args, **xargs):
        super().disconnect(*args, **xargs)
        self.on_disconnected()

    def mainloop_hook(self):
        if self.connected:
            super().mainloop_hook()
            if self._pulse is not None and self._next_pulse < datetime.now():
                self._next_pulse = datetime.now() + timedelta(seconds=30)
                try: self.send(self._pulse)
                except ConnectionError: pass
        else:
            try: self.connect()
            except ConnectionError: return self._stoploop.wait(3)


class SocketServer(_IO, socket_tools.Server, AbstractServer):
    init_args_help = ("//LISTEN_IP", "LISTEN_PORT")

    def __init__(self, listen_host="127.0.0.1", listen_port=0, *args, linebreak=b"\r", verbose=1, **xargs):
        if listen_host.startswith("//"): listen_host = listen_host[2:]
        super().__init__(host=listen_host, port=int(listen_port), *args, **xargs, verbose=verbose)
        self._break = linebreak

    def new_attached_client(self, *args, **xargs):
        client = super().new_attached_client(None, *args, **xargs)
        def on_enter():
            client.address = self._sockets["main"].getsockname()
            if client.connected:
                client.disconnect()
                client.connect()
            client.update_uri()
        self.bind(enter=on_enter)
        return client

    def enter(self):
        super().enter()
        self.update_uri()
        if self.verbose >= 1:
            print(f"[{self.__class__.__name__}] Operating on {self.uri}", file=sys.stderr)


class SocketScheme(AbstractScheme):
    Server = SocketServer
    Client = SocketClient

