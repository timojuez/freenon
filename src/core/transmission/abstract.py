"""
The classes AbstractClient and SocketClient help you to stay synchronised with
remote values. They support shared variables. See shared_vars.py.
"""

import sys, re, traceback
from abc import ABCMeta
from urllib.parse import parse_qsl
from datetime import datetime, timedelta
from ..util import log_call, Bindable, AbstractMainloopManager
from .types import SchemeType, ServerType, ClientType
from .discovery import DiscoverySchemeMixin
from . import shared_vars


class AbstractTarget(Bindable, AbstractMainloopManager):
    """ A server or client instance """
    verbose = 0
    connected = False
    uri = ""
    scheme_id = "[undefined]"
    Scheme = None
    shared_vars = shared_vars.SharedVars()
    shared_var_categories = property(lambda self: self.Scheme.shared_var_categories)

    def __init__(self, *args, verbose=0, **xargs):
        self.verbose = verbose
        self.update_uri()
        self.shared_vars = self.shared_vars.__class__()
        self._pending = []
        # apply @shared_vars to self
        for Var in self.Scheme.shared_vars.values(): Var(self)
        super().__init__(*args, **xargs)

    def __eq__(self, target):
        return (isinstance(target, AbstractTarget)
            and self.uri == target.uri
            and isinstance(self, self.Scheme.Client) == isinstance(target, self.Scheme.Client))

    def update_uri(self, *args): self.uri = ":".join(map(str, [self.scheme_id, *args]))

    def poll_shared_var_value(self, var, *args, **xargs):
        """ Called when a shared variable value is being requested """
        raise NotImplementedError()

    def on_receive_shared_var_value(self, var, value):
        """ Called when a value is being received from the other side """
        raise NotImplementedError()

    def set_shared_var_value(self, var, value):
        """ Set a value through the framework. Usually, on a client this will call var.remote_set() """
        raise NotImplementedError()

    def schedule(self, func, args=tuple(), kwargs={}, requires=tuple()):
        """ Use this to call methods that use Target.shared_vars.
        Call func(var_1, ..., var_n, *args, **xargs) if all n vars in @requires are set.
        Poll vars and schedule func otherwise. """
        if not self.connected: return
        try: vars_ = [self.shared_vars[name] for name in requires]
        except KeyError as e:
            if self.verbose > 3:
                print("[%s] Warning: Target does not provide shared vars required by `%s`: %s"
                %(self.__class__.__name__, func.__name__, e), file=sys.stderr)
            return
        return shared_vars.FunctionCall(self, func, args, kwargs, vars_)

    def mainloop_hook(self):
        super().mainloop_hook()
        for p in self._pending.copy():
            p.check_expiration()
            p.try_call()

    @log_call
    def on_shared_var_change(self, var_id, value):
        """ shared variable on server has changed """
        if var_id and self.verbose > 2:
            print("[%s] $%s = %s"%(self.__class__.__name__, var_id, repr(value)))
        
    def send(self, data): raise NotImplementedError()

    def on_receive_raw_data(self, data):
        consumed = [var.consume([data]) for var_id, var in self.shared_vars.items() if var.matches(data)]
        if not consumed: self.shared_vars.fallback.consume([data])

    def handle_uri_path(self, uri):
        if uri.path.startswith("/get/") and (var := self.shared_vars.get(uri.path[len("/get/"):])):
            print(var.get_wait())
        elif uri.path in ("/", "", "/set"):
            for key, val in parse_qsl(uri.query[1:], True):
                if val: # ?fkey=val
                    var = self.shared_vars[key]
                    convert = {bool: lambda s:s[0].lower() in "yt1"}.get(var.type, var.type)
                    self.set_shared_var_value(var, convert(val))
                else: self.send(key) # ?COMMAND #FIXME: use self.on_receive_raw_data for server
        else:
            print("404")


class AttachedClientMixin:
    """ This client class automatically connects to an internal server instance """
    _server = None
    _control_server = False

    def enter(self):
        if control_server := not self._server.connected: self._server.start()
        self._control_server = control_server
        super().enter()

    def exit(self):
        super().exit()
        if self._control_server: self._server.stop()


class AbstractServer(ServerType, AbstractTarget):
    init_args_help = None # tuple

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        for var in self.shared_vars.values(): var.init_on_server()
        for var in self.shared_vars.values():
            not var.id=="fallback" and var.bind(on_change=lambda *_,var=var: self.connected and var.resend())
    
    def enter(self):
        self.connected = True
        return super().enter()

    def exit(self):
        super().exit()
        self.connected = False

    def new_attached_client(self, *args, **xargs):
        """ return new Client instance that connects to this server. Should be overwritten in inheriting classes """
        Client = self.Scheme._new_target(self.Scheme.Client)
        AttachedClient = type(Client.__name__, (AttachedClientMixin, Client), {"_server":self})
        return AttachedClient(*args, **xargs)

    def set_shared_var_value(self, var, value): return var.set(value)

    def poll_shared_var_value(self, var, *args, **xargs): var.poll_on_server()

    def on_receive_shared_var_value(self, var, value): var.set_on_server(value)

    def on_receive_raw_data(self, data):
        if self.verbose >= 2: print(f"{self.uri} > ${repr(data)}")
        called_vars = [var for var_id, var in self.shared_vars.items() if var.call == data]
        if called_vars:
            # data is a request
            for var in called_vars:
                if var.is_set(): var.resend()
                else: self.poll_shared_var_value(var)
        else:
            # data is a command
            super().on_receive_raw_data(data)

    def send(self, data):
        if self.verbose >= 2: print(data)


class GroupedSet:
    """ This builds a list [*elements_of_set_1, *elements_of_set_2, ...].
    You can access set_n using the index n on this object. """

    def __init__(self, obj=None):
        if isinstance(obj, type(self)): self.data = obj.data.copy()
        else:
            self.data = {}
            if obj: self.update(obj)

    def add(self, obj, group=0):
        self[group].add(obj)

    def update(self, objs, group=0):
        self[group].update(objs)

    def __getitem__(self, key):
        r = self.data[key] = self.data.get(key, set())
        return r

    def __delitem__(self, key): del self.data[key]

    def __iter__(self):
        def iter():
            for group, s in sorted(self.data.items(), reverse=True):
                for e in s: yield e
        return iter()


class _PreloadMixin:
    preload_shared_vars = GroupedSet() # shared_var ids to be polled constantly when not set
    _preload_shared_vars_iter = None
    _preload_iteration_completed = False
    _preload_timeout = None
    _send_count = 0

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.preload_shared_vars = GroupedSet(self.preload_shared_vars)

    def on_connect(self):
        super().on_connect()
        self._preload_iteration_completed = False
        self._preload_shared_vars_iter = None

    def mainloop_hook(self):
        super().mainloop_hook()
        if not self.connected: return
        if not self._preload_iteration_completed:
            self._preload(10)
        else:
            if self._preload_timeout and self._preload_timeout > datetime.now(): return
            self._preload_timeout = datetime.now()+timedelta(seconds=1)
            self._preload(2)

    def _preload(self, max_polls):
        if not self._preload_shared_vars_iter: self._preload_shared_vars_iter = iter(self.preload_shared_vars)
        self._send_count = 0
        for _ in range(max_polls*100):
            try: f_id = next(self._preload_shared_vars_iter)
            except StopIteration:
                self._preload_shared_vars_iter = None
                self._preload_iteration_completed = True
                break
            if (f := self.shared_vars.get(f_id)) and not f.is_set():
                try: f.async_poll()
                except ConnectionError: break
            if self._send_count >= max_polls: break

    def send(self, *args, **xargs):
        super().send(*args, **xargs)
        self._send_count += 1


class _SharedVarsMixin:
    _poll_timeout = dict

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._poll_timeout = self._poll_timeout()

    def on_disconnected(self):
        super().on_disconnected()
        self._pending.clear()
        self._poll_timeout.clear()
        for var in self.shared_vars.values(): var.unset()

    def poll_shared_var_value(self, var, force=False):
        """ poll shared variable value if not polled in same time frame or force is True """
        if not force and (timeout := self._poll_timeout.get(var.call)) and timeout > datetime.now(): return
        self._poll_timeout[var.call] = datetime.now()+timedelta(seconds=30)
        var.poll_on_client()

    def on_receive_shared_var_value(self, var, value): var.set(value)

    def set_shared_var_value(self, var, value): var.remote_set(value)


class _AbstractClient(ClientType, AbstractTarget):
    """
    Abstract Client
    Note: Event callbacks (on_connect, on_shared_var_change) might be called in the mainloop
        and delay further command processing. Use threads for not blocking the
        mainloop.
    """
    init_args_help = None # tuple
    connected = False
    _connect_on_enter = False

    def __init__(self, *args, connect=True, **xargs):
        super().__init__(*args, **xargs)
        self._connect_on_enter = connect
    
    def enter(self):
        if self._connect_on_enter: self.connect()
        return super().enter()

    def mainloop_quit(self):
        super().mainloop_quit()
        self.disconnect()
        if self.connected: self.on_disconnected()

    def connect(self): pass

    def disconnect(self): pass

    def query(self, cmd, matches=None):
        """
        Low level function that sends @cmd and returns a value where matches(value) is True.
        Only called by hifish
        """
        if matches is None: return self.send(cmd)
        raise NotImplementedError()

    __call__ = lambda self,*args,**xargs: self.query(*args,**xargs)
        
    def on_receive_raw_data(self, data):
        if self.verbose > 4: print(data, file=sys.stderr)
        super().on_receive_raw_data(data)

    def send(self, data):
        if self.verbose > 4: print(f"{self.uri} > ${repr(data)}", file=sys.stderr)

    @log_call
    def on_connect(self):
        """ Execute when connected to server e.g. after connection aborted """
        self.connected = True
        if self.verbose > 0:
            print("[%s] connected to %s"%(self.__class__.__name__, self.uri), file=sys.stderr)
        
    @log_call
    def on_disconnected(self): self.connected = False

    def handle_uri_path(self, *args, **xargs):
        self.connect()
        super().handle_uri_path(*args, **xargs)


class AbstractClient(_PreloadMixin, _SharedVarsMixin, _AbstractClient): pass


class _AbstractSchemeMeta(ABCMeta):

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls.shared_vars = cls.shared_vars.copy()
        cls.shared_var_categories = cls.shared_var_categories.copy()

    # the following methods are only available on class

    def get_client_uri(cls):
        args = cls.client_args_help
        if args is None: args = getattr(cls.Client,"init_args_help",None)
        if args is not None: return ":".join((cls.scheme_id, *args))

    def get_server_uri(cls):
        args = cls.server_args_help
        if args is None: args = getattr(cls.Server,"init_args_help",None)
        if args is not None: return ":".join((cls.scheme_id, *args))

    def shared_var(cls, SharedVar=None, parent=None, overwrite=False):
        """
        This is a decorator to be used on shared variable class definitions that belong to the current class.
        @overwrite: If true, proceeds if a shared variable with same id already exists.
        Example:
            from shared_vars import SharedVar
            @AbstractScheme.shared_var
            class MySharedVar(SharedVar): pass
        """
        def add(SharedVar):
            if parent is None:
                Var = SharedVar
            elif cls.shared_vars.get(parent.id) != parent:
                raise ValueError(f"Parent {parent.id} does not exist in {cls}.")
            else:
                Var = SharedVar.as_child(parent)
            if not issubclass(Var, shared_vars.SharedVar):
                raise TypeError(f"Shared variable must be of type {shared_vars.SharedVar}")
            if Var.id.startswith("_"): raise KeyError("SharedVar.id may not start with '_'")
            if hasattr(cls.shared_vars.__class__, Var.id):
                raise KeyError("SharedVar.id `%s` is already occupied."%Var.id)
            if not overwrite and Var.id in cls.shared_vars:
                raise KeyError(
                    "SharedVar.id `%s` is already occupied. Use shared_var(overwrite=True)"%Var.id)
            cls.shared_vars.pop(Var.id, None)
            cls.shared_vars[Var.id] = Var
            cls.shared_var_categories[Var.category] = None
            return SharedVar
        return add(SharedVar) if SharedVar else add


class AbstractScheme(DiscoverySchemeMixin, SchemeType, metaclass=_AbstractSchemeMeta):
    title = None
    description = None
    Client = AbstractClient
    Server = AbstractServer
    client_args_help = None # tuple, if None, will be read from Client.init_args_help
    server_args_help = None # tuple
    shared_vars = shared_vars.SharedVars()
    shared_var_categories = dict()

    @classmethod
    def _new_target(cls, base):
        if issubclass(cls, AbstractTarget): raise TypeError(
            f"Cannot run method on concrete class. Call this on self.Scheme (class {cls.__name__}).")
        return type(cls.__name__, (cls, base), {"Scheme": cls})

    @classmethod
    def new_client(cls, *args, **xargs):
        return cls._new_target(cls.Client)(*args, **xargs)

    @classmethod
    def new_server(cls, *args, **xargs):
        return cls._new_target(cls.Server)(*args, **xargs)

    @classmethod
    def new_dummyserver(cls, *args, **xargs):
        """ Returns a server instance that stores bogus values """
        DummyServer = type("DummyServer", (DummyServerMixin, cls.Server), {})
        return cls._new_target(DummyServer)(*args, **xargs)

    @classmethod
    def get_title(cls): return cls.title or re.sub(r'(?<!^)(?=[A-Z])', ' ', cls.__name__)


class DummyServerMixin:
    """ Server class that fills shared variable's values with some values """

    def poll_shared_var_value(self, var, *args, **xargs): var.poll_on_dummy()

    def on_receive_shared_var_value(self, var, value):
        if isinstance(var, shared_vars.NumericVar) and not (var.min <= value <= var.max): return
        var.set(value)


@AbstractScheme.shared_var
class Fallback(shared_vars.OfflineVarMixin, shared_vars.SelectVar):
    """ Matches always, if no other shared variable matched """
    name = "Last Unexpected Message"

    def consume(self, data):
        for data_ in data:
            if self.target.verbose > 1:
                print("[%s] WARNING: could not parse `%s`"%(self.__class__.__name__, data_))
            with self._lock:
                self._prev_val = self._val
                self._val = data_
                self.on_change(data_)
                if self._prev_val == None: self.on_set()
                self.on_processed(data_)


@AbstractScheme.shared_var
class Name(shared_vars.OfflineVarMixin, shared_vars.SelectVar):
    
    def get(self): return self.target.Scheme.get_title()
    def is_set(self): return True
    def unset(self): pass

