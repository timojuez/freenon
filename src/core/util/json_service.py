"""
The JsonService can be used for interprocess communication. It receives dicts.
The function "send" sends dicts.
"""

import selectors, socket, json, sys
from threading import Thread
from . import AbstractMainloopManager


PORT=654321


class Service(AbstractMainloopManager):
    """
    A service communicating with Json objects. Call enter() after init.
    """
    EVENTS = selectors.EVENT_READ
    
    def __init__(self, host="127.0.0.1", port=PORT, verbose=0):
        super().__init__()
        self.address = (host, port)
        self._verbose = verbose

    host = property(lambda self: self.sock.getsockname()[0])
    port = property(lambda self: self.sock.getsockname()[1])

    def enter(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(self.address)
        if self._verbose > 0: print(
            "[%s] Listening on %s:%d"%(self.__class__.__name__,*self.sock.getsockname()), file=sys.stderr)
        self.sock.listen(100)
        self.sock.setblocking(False)
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.sock, selectors.EVENT_READ, self.accept)
        self._socket_read, self._sock_write = socket.socketpair()
        self.sel.register(self._socket_read, selectors.EVENT_READ)
        return super().enter()

    def break_select(self):
        self._sock_write.send(b"\x00")

    def mainloop_quit(self):
        super().mainloop_quit()
        self.sock.shutdown(socket.SHUT_RDWR)

    def exit(self):
        super().exit()
        for sock in [self.sock, self._socket_read, self._sock_write]:
            sock.close()

    def mainloop_hook(self):
        super().mainloop_hook()
        events = self.sel.select(5)
        for key, mask in events:
            if key.fileobj is self._socket_read: # called break_select()
                self._socket_read.recv(1)
                break
            callback = key.data
            callback(key.fileobj, mask)

    def accept(self, sock, mask):
        try: conn, addr = sock.accept()
        except OSError as e:
            if self._verbose > 1: print(repr(e), file=sys.stderr)
            return
        conn.setblocking(False)
        self.sel.register(conn, self.EVENTS, self.connection)
        
    def connection(self, conn, mask):
        if mask & selectors.EVENT_READ:
            try: data = conn.recv(1000)
            except ConnectionError as e:
                print(e, file=sys.stderr)
                data = None
            if data: self.read(data)
            else:
                self.sel.unregister(conn)
                conn.close()
        if mask & selectors.EVENT_WRITE: self.write(conn)

    def read(self, data): pass
    def write(self, conn): pass
    

class JsonService(Service):

    def read(self, data):
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
    sock.send(json.dumps(obj).encode())

