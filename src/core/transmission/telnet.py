import time, socket, time, selectors, traceback, sys
from telnetlib import Telnet, TELNET_PORT
from threading import Lock, Thread, Event
from contextlib import suppress
from ..util.json_service import Server
from .abstract import AbstractScheme, AbstractClient, AbstractServer


class TelnetClient(AbstractClient):
    """
    This class connects to the server via LAN and executes commands
    @host is the server's hostname or IP.
    """
    init_args_help = ("//SERVER_IP", "SERVER_PORT")
    host = None
    port = None
    _pulse = "" # this is being sent regularly to keep connection
    _telnet = None
    _send_lock = Lock
    _pulse_stop = Event
    _connect_lock = Lock
    
    def __init__(self, host, port=TELNET_PORT, *args, **xargs):
        super().__init__(*args, **xargs)
        self._send_lock = self._send_lock()
        self._connect_lock = self._connect_lock()
        self._pulse_stop = self._pulse_stop()
        if host: self._update_vars(host, port)

    def _update_vars(self, host, port):
        if host.startswith("//"): host = host[2:]
        self.host = host
        self.port = port
        self.update_uri(f"//{host}", port)
    
    def send(self, cmd):
        super().send(cmd)
        try:
            with self._send_lock:
                assert(self.connected and self._telnet.sock)
                self._telnet.write(("%s\r"%cmd).encode("ascii"))
                time.sleep(.01)
        except (OSError, EOFError, AssertionError, AttributeError) as e:
            self.on_disconnected()
            raise BrokenPipeError(e)
        
    def read(self, timeout=None):
        try:
            assert(self.connected and self._telnet.sock)
            return self._telnet.read_until(b"\r",timeout=timeout).strip().decode()
        except (socket.timeout, UnicodeDecodeError): return None
        except (OSError, EOFError, AssertionError, AttributeError) as e:
            self.on_disconnected()
            raise BrokenPipeError(e)
    
    def connect(self):
        super().connect()
        with self._connect_lock:
            if self.connected: return
            try: self._telnet = Telnet(self.host,self.port,timeout=2)
            except (ConnectionError, socket.timeout, socket.gaierror, socket.herror, OSError) as e:
                raise ConnectionError(e)
            else: self.on_connect()

    def disconnect(self):
        super().disconnect()
        with suppress(AttributeError, OSError):
            self._telnet.sock.shutdown(socket.SHUT_WR) # break read()
            self._telnet.close()
    
    def on_connect(self):
        super().on_connect()
        def func():
            while not self._pulse_stop.wait(10):
                try: self.send(self._pulse)
                except ConnectionError: pass
        self._pulse_stop.clear()
        if self._pulse is not None: Thread(target=func, daemon=True, name="pulse").start()
        
    def on_disconnected(self):
        super().on_disconnected()
        self._pulse_stop.set()
        
    def mainloop_hook(self):
        super().mainloop_hook()
        if self.connected:
            try: data = self.read(5)
            except ConnectionError: pass
            else:
                if data: self.on_receive_raw_data(data)
        else:
            try: self.connect()
            except ConnectionError: return self._stoploop.wait(3)


class TelnetServer(Server, AbstractServer):
    init_args_help = ("//LISTEN_IP", "LISTEN_PORT")
    
    def __init__(self, listen_host="127.0.0.1", listen_port=0, *args, linebreak="\r", verbose=1, **xargs):
        if listen_host.startswith("//"): listen_host = listen_host[2:]
        super().__init__(host=listen_host, port=listen_port, *args, **xargs, verbose=verbose)
        self._break = linebreak
        if self.verbose >= 1:
            print(f"[{self.__class__.__name__}] Operating on {self.uri}", file=sys.stderr)

    def new_attached_client(self, *args, **xargs):
        client = super().new_attached_client(None, *args, **xargs)
        def on_enter():
            client._update_vars(self.host, self.port)
            if client.connected:
                client.disconnect()
                client.connect()
        self.bind(enter=on_enter)
        return client

    def read(self, data, conn):
        try: decoded = data.strip().decode()
        except: return print(traceback.format_exc())
        for data in decoded.replace("\n","\r").split("\r"):
            if self.verbose >= 1: print("%s $ %s"%(self.uri, data))
            try: self.on_receive_raw_data(data)
            except Exception as e: print(traceback.format_exc())

    def send(self, data):
        if self.verbose >= 1: print(data)
        encoded = ("%s%s"%(data, self._break)).encode("ascii")
        self.write(encoded)


class TelnetScheme(AbstractScheme):
    Server = TelnetServer
    Client = TelnetClient

