"""
The JsonService can be used for interprocess communication. It receives dicts.
The function "send" sends dicts.
"""

import selectors, socket, json, sys, traceback
from threading import Thread, Lock
from contextlib import suppress
from . import AbstractMainloopManager


PORT=54321


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
        self._sockets["write"].settimeout(.2)
        self._connections = set()
        self.sel = selectors.DefaultSelector()
        self.sel.register(self._sockets["read"], selectors.EVENT_READ)
        return super().enter()

    def exit(self):
        super().exit()
        while self._sockets:
            name, sock = self._sockets.popitem()
            sock.close()

    def add_socket(self, sock):
        self.sel.register(sock, selectors.EVENT_READ, self.connection)
        self._connections.add(sock)

    def remove_socket(self, sock):
        try: self._connections.remove(sock)
        except KeyError as e: raise ValueError(e)
        self.sel.unregister(sock)
        try: sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        sock.close()

    def trigger_mainloop(self):
        try: wsock = self._sockets["write"]
        except KeyError:
            raise RuntimeError("No write socket found. Mainloop must be running when calling this method.")
        if self._triggering.acquire(blocking=False):
            try: wsock.sendall(b"\x00")
            except OSError as e:
                with suppress(RuntimeError): self._triggering.release()
                print(f"[{self.__class__.__name__}] {e} in trigger_mainloop()", file=sys.stderr)
            except:
                with suppress(RuntimeError): self._triggering.release()
                raise

    def mainloop_quit(self):
        super().mainloop_quit()
        self.trigger_mainloop()

    def mainloop_hook(self):
        super().mainloop_hook()
        events = self.sel.select(5)
        with suppress(RuntimeError): self._triggering.release()
        for key, mask in events:
            if key.fileobj is self._sockets["read"]: # called trigger_mainloop()
                try: self._sockets["read"].recv(1024)
                except OSError: pass
                break
            callback = key.data
            callback(key.fileobj, mask)

    def connection(self, conn, mask):
        try: data = conn.recv(1000)
        except OSError as e:
            print(e, file=sys.stderr)
            data = None
        if data:
            self.read(data, conn)
        else:
            self.remove_socket(conn)

    def read(self, data, conn): raise NotImplementedError()

    def write(self, msg, conn=None):
        if conn:
            try: conn.sendall(msg)
            except OSError: self.remove_socket(conn)
            except: traceback.print_exc()
        else:
            for conn in self._connections.copy(): self.write(msg, conn)


class Server(Base):

    def enter(self):
        try: return super().enter()
        finally: self.connect()

    def connect(self):
        self._sockets["main"] = socket.create_server(self.address, backlog=100)
        self._sockets["main"].setblocking(False)
        try: self._sockets["main"].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except: pass
        if self._verbose >= 2:
            print(f"[{type(self).__name__}] Listening on {self.host}:{self.port}", file=sys.stderr)
        self.sel.register(self._sockets["main"], selectors.EVENT_READ, self.accept)

    def accept(self, sock, mask):
        try: conn, addr = sock.accept()
        except OSError as e:
            if self._verbose > 1: print(repr(e), file=sys.stderr)
            return
        conn.setblocking(False)
        self.add_socket(conn)


class Client(Base):

    def connect(self, timeout=None):
        self._sockets["main"] = socket.create_connection(self.address, timeout=timeout)
        self._sockets["main"].setblocking(False)
        self._connections.clear()
        self.add_socket(self._sockets["main"])

    def disconnect(self):
        if sock := self._sockets.pop("main", None):
            try: self.remove_socket(sock)
            except ValueError: pass

    #def mainloop_hook(self):
    #    if self.pulse is not None:
    #        self.write(self.pulse)
    #    super().mainloop_hook()


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

