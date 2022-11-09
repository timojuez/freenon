import time, socket, time, selectors, traceback, sys
from telnetlib import Telnet, TELNET_PORT
from threading import Lock, Thread, Event
from contextlib import suppress
from ..util.json_service import Service
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


class _TelnetServer(Service):
    EVENTS = selectors.EVENT_READ | selectors.EVENT_WRITE
    
    def __init__(self, target, listen_host, listen_port, linebreak="\r", verbose=0):
        self._send = {}
        self.verbose = verbose
        self.target = target
        self._break = linebreak
        if self.verbose >= 1:
            print(f"[{self.__class__.__name__}] Operating on {self.target.uri}", file=sys.stderr)
        super().__init__(host=listen_host, port=listen_port, verbose=1)

    def connection(self, conn, mask):
        if conn not in self._send: self._send[conn] = b""
        return super().connection(conn, mask)

    def read(self, data):
        try: decoded = data.strip().decode()
        except: return print(traceback.format_exc())
        for data in decoded.replace("\n","\r").split("\r"):
            if self.verbose >= 1: print("%s $ %s"%(self.target.uri,data))
            try: self.target.on_receive_raw_data(data)
            except Exception as e: print(traceback.format_exc())
        
    def write(self, conn):
        time.sleep(.05)
        if not self._send[conn]: return
        l = len(self._send[conn])
        try: conn.sendall(self._send[conn][:l])
        except OSError: pass
        self._send[conn] = self._send[conn][l:]
    
    def on_target_send(self, data):
        if self.verbose >= 1: print(data)
        encoded = ("%s%s"%(data,self._break)).encode("ascii")
        # send to all connected listeners
        for conn in self._send: self._send[conn] += encoded


class TelnetServer(AbstractServer):
    init_args_help = ("//LISTEN_IP", "LISTEN_PORT")
    _server = None
    
    def __init__(self, listen_host="127.0.0.1", listen_port=0, linebreak="\r", *args, verbose=0, **xargs):
        super().__init__(*args, verbose=max(0, verbose-1), **xargs)
        if listen_host.startswith("//"): listen_host = listen_host[2:]
        self._server = _TelnetServer(self, listen_host, int(listen_port), linebreak, verbose=verbose)
    
    host = property(lambda self: self._server.sock.getsockname()[0])
    port = property(lambda self: self._server.sock.getsockname()[1])

    def enter(self):
        self._server.start()
        super().enter()

    def exit(self):
        time.sleep(.1)
        super().exit()
        self._server.stop()

    def new_attached_client(self, *args, **xargs):
        client = super().new_attached_client(None, *args, **xargs)
        def on_enter():
            client._update_vars(self.host, self.port)
            if client.connected:
                client.disconnect()
                client.connect()
        self.bind(enter=on_enter)
        return client

    def send(self, data): return self._server.on_target_send(data)


class TelnetScheme(AbstractScheme):
    Server = TelnetServer
    Client = TelnetClient

