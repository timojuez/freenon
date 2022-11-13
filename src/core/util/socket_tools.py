"""
The JsonService can be used for interprocess communication. It receives dicts.
The function "send" sends dicts.
"""

import selectors, socket, json, sys
from threading import Thread, Lock
from queue import Queue, Empty
from . import AbstractMainloopManager


PORT=654321


class Base(AbstractMainloopManager):
    """
    Call enter() after init.
    """

    def __init__(self, host="127.0.0.1", port=PORT, *args, verbose=0, **xargs):
        self.address = (host, port)
        self._sockets = {}
        self._triggering = Lock()
        self._verbose = verbose
        super().__init__(*args, **xargs)

    def _get_sock_name(self, i):
        if sock := self._sockets.get("main"): return sock.getsockname()[i]
        else: return self.address[i]

    host = property(lambda self: self._get_sock_name(0))
    port = property(lambda self: self._get_sock_name(1))

    def enter(self):
        self._sockets["read"], self._sockets["write"] = socket.socketpair()
        self._send_queue = {}
        self.sel = selectors.DefaultSelector()
        self.sel.register(self._sockets["read"], selectors.EVENT_READ)
        return super().enter()

    def exit(self):
        super().exit()
        while self._sockets:
            name, sock = self._sockets.popitem()
            sock.close()

    def connect(self): pass

    def disconnect(self, conn=None):
        if sock := conn or self._sockets.pop("main", None):
            self.sel.unregister(sock)
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            sock.close()
            try: del self._send_queue[sock]
            except KeyError: pass

    def trigger_mainloop(self):
        if self._triggering.acquire(blocking=False):
            self._sockets["write"].send(b"\x00")

    def mainloop_quit(self):
        super().mainloop_quit()
        self.trigger_mainloop()

    def mainloop_hook(self):
        super().mainloop_hook()
        events = self.sel.select(5)
        for key, mask in events:
            if key.fileobj is self._sockets["read"]: # called trigger_mainloop()
                self._sockets["read"].recv(1)
                self._triggering.release()
                break
            callback = key.data
            callback(key.fileobj, mask)
        for conn, queue in self._send_queue.copy().items():
            for _ in range(50):
                try: msg = queue.get(block=False)
                except Empty: break
                else:
                    try: conn.sendall(msg)
                    except (OSError, ConnectionError):
                        self.disconnect(conn)
                        break

    def connection(self, conn, mask):
        try: data = conn.recv(1000)
        except ConnectionError as e:
            print(e, file=sys.stderr)
            data = None
        if data:
            self.read(data, conn)
        else:
            self.disconnect(conn)

    def read(self, data, conn): raise NotImplementedError()

    def write(self, msg, conn=None):
        if conn:
            self._send_queue[conn].put(msg)
        else:
            for conn, queue in self._send_queue.copy().items():
                queue.put(msg)
        self.trigger_mainloop()


class Server(Base):

    def enter(self):
        try: return super().enter()
        finally: self.connect()

    def connect(self):
        super().connect()
        self._sockets["main"] = socket.create_server(self.address, backlog=100)
        self._sockets["main"].setblocking(False)
        try: self._sockets["main"].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except: pass
        if self._verbose > 0:
            print(f"[{type(self).__name__}] Listening on {self.host}:{self.port}", file=sys.stderr)
        self.sel.register(self._sockets["main"], selectors.EVENT_READ, self.accept)

    def accept(self, sock, mask):
        try: conn, addr = sock.accept()
        except OSError as e:
            if self._verbose > 1: print(repr(e), file=sys.stderr)
            return
        conn.setblocking(False)
        self._send_queue[conn] = Queue()
        self.sel.register(conn, selectors.EVENT_READ, self.connection)


class Client(Base):

    def connect(self, timeout=None):
        super().connect()
        self._sockets["main"] = socket.create_connection(self.address, timeout=timeout)
        self._sockets["main"].setblocking(False)
        self._send_queue.clear()
        self._send_queue[self._sockets["main"]] = Queue()
        self.sel.register(self._sockets["main"], selectors.EVENT_READ, self.connection)


class JsonService(Server):

    def read(self, data, conn):
        try:
            d = json.loads(data.decode())
            if self._verbose > 1: print(
                "[%s] Received %s"%(self.__class__.__name__,d), file=sys.stderr)
        except Exception as e: print(repr(e))
        else: self.on_read(d)

    def on_read(self, data): pass


class RemoteControlService(JsonService):
    """
    Opens a service on a port and executes calls on @obj when received
    message schema: {"func": property_of_obj, "kwargs": {}}
    """

    def __init__(self, obj, func_whitelist=None, *args, **xargs):
        self._obj = obj
        self._func_whitelist = func_whitelist
        super().__init__(*args,**xargs)

    def on_read(self, data):
        try:
            if self._func_whitelist: assert(data["func"] in self._func_whitelist)
            #assert(isinstance(data["kwargs"]["button"],bool))
            func = self._obj
            for attr in data["func"].split("."): func = getattr(func,attr)
            kwargs = data["kwargs"]
        except:
            return print("[%s] invalid message."%self.__class__.__name__, file=sys.stderr)
        Thread(name=self._obj.__class__.__name__, target=func,kwargs=kwargs,
            daemon=True).start()


def send(obj, port=PORT):
    sock = socket.socket()
    sock.connect_ex(("localhost", port))
    sock.sendall(json.dumps(obj).encode())

