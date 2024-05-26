import sys, traceback, re, math
from contextlib import suppress
from decimal import Decimal
from threading import Event, Lock, RLock, Timer, Thread
from datetime import datetime, timedelta
from ..util import call_sequence, Bindable, AttrDict
from .types import ClientType, ServerType


MAX_CALL_DELAY = 2 #seconds, max delay for calling function using "@require"


class FunctionCall(object):
    """ Function call that requires shared variables. Drops call if no connection """

    def __init__(self, target, func, args=tuple(), kwargs={}, required_vars=tuple(), timeout=MAX_CALL_DELAY):
        self._lock = Lock()
        self._target = target
        self._func = func
        self._vars = required_vars
        self._args = args
        self._kwargs = kwargs
        self._timeout = datetime.now()+timedelta(seconds=timeout) if timeout != None else None
        self.postpone()
        try: [var.async_poll() for var in self._missing_vars]
        except ConnectionError: self.cancel()

    def __repr__(self): return "<pending%s>"%self._func

    _missing_vars = property(lambda self: list(filter(lambda var:not var.is_set(), self._vars)))

    def try_call(self):
        with self._lock:
            if not self.active: return False
            if not self._missing_vars:
                try: self._func(*self._vars, *self._args, **self._kwargs)
                except ConnectionError: pass
                except: traceback.print_exc()
                finally: self.cancel()
                return True

    def postpone(self): self._target._pending.append(self)

    def cancel(self):
        with suppress(ValueError): self._target._pending.remove(self)

    active = property(lambda self: self in self._target._pending)

    expired = property(lambda self: self._timeout and self._timeout < datetime.now())

    def check_expiration(self):
        if self.expired and self._target.verbose > 1:
            print("[%s] pending function `%s` expired"
                %(self.__class__.__name__, self._func.__name__), file=sys.stderr)
            self.cancel()
    
    def on_shared_var_set(self, var):
        if var in self._vars and self.try_call():
            if self._target.verbose > 5: print("[%s] called pending function %s"
                %(self.__class__.__name__, self._func.__name__), file=sys.stderr)


class SharedVars(AttrDict):
    
    def wait_for(self, *shared_vars):
        try: shared_vars = [var if isinstance(var, SharedVar) else self[var] for var in shared_vars]
        except KeyError as e:
            print(f"[{self.__class__.__name__}] Warning: Target does not provide shared variable. {e}",
                file=sys.stderr)
            return False
        threads = [Thread(target=var.wait_poll, daemon=True, name="wait_for") for var in shared_vars]
        for t in threads: t.start()
        for t in threads: t.join()
        return all([var.is_set() for var in shared_vars])
        

class SharedVarInterface(object):
    name = "Short description"
    category = "Misc"
    call = None # for retrieval, call target.send(call)
    default_value = None # if no response from server
    dummy_value = None # for dummy server
    type = object # value data type, e.g. int, bool, str
    #id = "id" # variable will be available as target.shared_vars.id; default: id = class name

    def init_on_server(self):
        """ called after __init__ on server side """
        pass

    def poll_on_server(self):
        """ This is being executed on server side when the client asks for a value
        and must call self.set(some value) """
        raise NotImplementedError()
    
    def set_on_server(self, value):
        """ This is being executed on server side when the client tries to set a value.
        It shall call self.set(value) """
        raise NotImplementedError()
    
    def matches(self, data):
        """
        @data: line received from target
        return True if data shall be parsed with this class
        """
        raise NotImplementedError()
        
    def serialize(self, value):
        """ transform @value to list of strings """
        return [value]

    def unserialize(self, data):
        """ transform list of strings @data to type self.type """
        return data


class _MetaVar(type):

    def __init__(cls, name, bases, dct):
        if "id" not in dct:
            cls.id = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        if "name" not in dct:
            cls.name = re.sub(r'(?<!^)(?=[A-Z])', ' ', cls.__name__)
            cls.name = " ".join(["%s%s"%(x[0].upper(),x[1:]) if len(x)>0 else "" for x in cls.name.split("_")])

        
class AsyncSharedVar(SharedVarInterface, Bindable, metaclass=_MetaVar):
    """
    A target attribute for high level communication
    If being used in a with statement, the value will not change during execution of the inside code.
    
    Warning: Calling get() in the event callbacks can cause deadlocks.
        Instead, get the value from the function parameter.
    """
    name = None
    parent = None
    _val = None
    _prev_val = None
    _block_on_remote_set = None
    _block_on_remote_set_resetter = None
    _lock = RLock
    _event_on_set = Event

    def __init__(self, target):
        super().__init__()
        target_type = (ServerType, ClientType)
        if not any([isinstance(target, c) for c in target_type]):
            raise TypeError("target must inherit one of %s."%(", ".join(map(lambda c:c.__name__, target_type))))
        self.target = target
        self._buffer = []
        self._lock = self._lock()
        self._event_on_set = self._event_on_set()
        self.children = []
        target.shared_vars[self.id] = self
        
    def __str__(self):
        with self: return str(self.get()) if self.is_set() else "..."

    def __enter__(self):
        self._lock.__enter__()
        return self

    def __exit__(self, *args, **xargs):
        self._lock.__exit__(*args, **xargs)

    @classmethod
    def as_child(cls, parent):
        class Child(cls):
            id = cls.id
            name = cls.name
            call = property(lambda self: self.parent.call)

            def __init__(self, *args, **xargs):
                super().__init__(*args, **xargs)
                self.parent = self.target.shared_vars[parent.id]
                self.parent.children.append(self.id)

            def matches(self, data):
                return self.parent.matches(data) and super().matches(self.parent.unserialize([data]))

            def poll_on_client(self, *args, **xargs):
                self.parent.poll_on_client(*args, **xargs)

            def _send(self, *args, **xargs):
                if issubclass(self.target.__class__, ServerType):
                    self.parent.resend()
                else:
                    super()._send(*args, **xargs)

            def serialize(self, value):
                return [y for x in super().serialize(value) for y in self.parent.serialize(x)]

            def unserialize(self, data):
                # split data into chunks as small as possible so that parent.is_complete(chunk) is True
                # and pass to parent.unserialize()
                buf = []
                output = []
                while data:
                    buf.append(data.pop(0))
                    if self.parent.is_complete(buf):
                        output.append(self.parent.unserialize(buf))
                        buf.clear()
                if buf: raise ValueError(f"{buf} could not be unserialized by {self.parent.id}")
                return super().unserialize(output)
        return Child

    def get(self):
        if not self.is_set(): raise ConnectionError(f"`{self.id}` not available. Use Target.schedule")
        else: return self._val
    
    def remote_set(self, value, force=False):
        """ request update to @value on other side """
        if value is None: raise ValueError("Value may not be None")
        if not force and not isinstance(value, self.type):
            print("WARNING: Value %s is not of type %s."%(repr(value),self.type.__name__), file=sys.stderr)
        serialized = self.serialize(self.type(value))
        if not self._blocked(serialized): self._send(serialized)

    def _send(self, serialized):
        self.on_send()
        for data in serialized: self.target.send(data)

    def _blocked(self, serialized):
        """ prevent sending the same line many times """
        if self._block_on_remote_set == serialized: return True
        self._block_on_remote_set = serialized
        try: self._block_on_remote_set_resetter.cancel()
        except AttributeError: pass
        self._block_on_remote_set_resetter = Timer(1, lambda: setattr(self, "_block_on_remote_set", None))
        self._block_on_remote_set_resetter.start()
    
    def is_set(self): return self._val != None
        
    def unset(self):
        with self._lock:
            self._val = None
            self.on_unset()
        #with suppress(ValueError): self.target._polled.remove(self.call)

    def async_poll(self, *args, **xargs): self.target.poll_shared_var_value(self, *args, **xargs)

    def poll_on_client(self):
        """ async_poll() executed on client side """
        if self.default_value is not None:
            self._timer_set_default = Timer(MAX_CALL_DELAY, self._set_default)
            self._timer_set_default.start()
        if self.call is not None: self.target.send(self.call)
    
    def poll_on_dummy(self):
        if self.dummy_value is not None: val = self.dummy_value
        elif self.default_value is not None: val = self.default_value
        else: raise ValueError("Shared variable %s has no dummy value."%self.id)
        #self.on_receive_raw_data(self.serialize(val)) # TODO: handle cases where var.call matches but var.matches() is False and maybe var'.matches() is True
        self.set(val)

    def _set_default(self):
        with self._lock:
            if not self.is_set(): self._set(self.default_value)
    
    def resend(self):
        self._send(self.serialize(self.get()))

    def is_complete(self, buf):
        """ @buf list, returns True if l contains all parts and can be unserialized """
        return True

    def consume(self, data):
        """ unserialize and apply @data to this object """
        self._buffer.extend(data)
        if not self.is_complete(self._buffer):
            if isinstance(self.target, ServerType): self._buffer.clear()
            return
        data = self._buffer.copy()
        self._buffer.clear()
        self.__class__._block_on_remote_set = None # for power.consume("PWON")
        try:
            d = self.unserialize(data)
            return self.target.on_receive_shared_var_value(self, d)
        except:
            print(f"Error on {self.id}.consume({repr(data)}):", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

    def set(self, value):
        with self._lock: return self._set(value)
    
    def _set(self, value):
        assert(value is not None)
        if self.type and not isinstance(value, self.type):
            raise TypeError(f"Value for {self.id} is not of type {self.type.__name__}: {repr(value)}")
        self._prev_val = self._val
        self._val = value
        if not self.is_set(): return
        if self._val != self._prev_val: self.on_change(self._val)
        if self._prev_val == None: self.on_set()
        self.on_processed(value)

    def bind(self, on_change=None, on_set=None, on_unset=None, on_processed=None, on_send=None):
        """ Register an observer with bind() and call the callback as soon as possible
        to stay synchronised """
        with self._lock:
            if self.is_set():
                if on_change: on_change(self.get())
                if on_set: on_set()
                if on_processed: on_processed(self.get())
            elif on_unset: on_unset()
            
            if on_change: super().bind(on_change = on_change)
            if on_set: super().bind(on_set = on_set)
            if on_unset: super().bind(on_unset = on_unset)
            if on_processed: super().bind(on_processed = on_processed)
            if on_send: super().bind(on_send = on_send)
            
    def on_change(self, val):
        """ This event is being called when self.options or the return value of self.get() changes """
        self.target.on_shared_var_change(self.id, val)
    
    def on_set(self):
        """ Event is fired on initial set """
        try: self._timer_set_default.cancel()
        except: pass
        self._event_on_set.set()
        if getattr(self.target, "_pending", None):
            if self.target.verbose > 5: print("[%s] %d pending functions"
                %(self.target.__class__.__name__, len(self.target._pending)), file=sys.stderr)
            if self.target.verbose > 6: print("[%s] pending functions: %s"
                %(self.target.__class__.__name__, self.target._pending), file=sys.stderr)
            for call in self.target._pending.copy(): # on_shared_var_set() changes _pending
                call.on_shared_var_set(self)
        
    def on_unset(self):
        try: self._timer_set_default.cancel()
        except: pass
        self._event_on_set.clear()
    
    def on_processed(self, value):
        """ This event is being called each time the variable is being set to a value
        even if the value is the same as the previous one """
        pass

    def on_send(self):
        """ This event is being fired when a value update has been sent to remote """
        pass


class SynchronousSharedVar(AsyncSharedVar):

    def __init__(self,*args,**xargs):
        self._poll_lock = Lock()
        super().__init__(*args,**xargs)

    def get_wait(self):
        with self._poll_lock:
            try: return super().get()
            except ConnectionError:
                if self.wait_poll(): return super().get()
                else: raise ConnectionError("Timeout on waiting for answer for %s"%self.id)

    def wait_poll(self, force=False):
        """ Poll and wait if variable is unset. Returns False on timeout and True otherwise """
        if not self.target.connected: return False
        if force: self.unset()
        if not self.is_set():
            try: self.async_poll(force)
            except ConnectionError: return False
            if not self._event_on_set.wait(timeout=MAX_CALL_DELAY+.1): return False
        return True


SharedVar = SynchronousSharedVar

class NumericVar(SharedVar):
    min=0
    max=99


class IntVar(NumericVar):
    type=int
    dummy_value = property(lambda self: self.default_value or math.ceil((self.max+self.min)/2))


class SelectVar(SharedVar):
    type=str
    translation = {} #{return_string:value} unserialize return_string to value / serialize vice versa
    translation_inversed = property(lambda self: {val:key for key,val in self.translation.items()})
    options = property(lambda self: list(self.translation.values()))
    dummy_value = property(lambda self: self.default_value or (self.options[0] if self.options else "?"))

    def serialize(self, val): return [self.translation_inversed.get(val,val)]

    def unserialize(self, data): return [self.translation.get(val,val) for val in data]

    def remote_set(self, value, force=False):
        if not force and value not in self.options:
            raise ValueError(
                "Value must be one of %s or try target.shared_vars.%s.remote_set(value, force=True)"
                %(self.options, self.id))
        return super().remote_set(value, force)


class BoolVar(SelectVar):
    type=bool
    options = [True, False]
    dummy_value = property(lambda self: self.default_value or False)


class DecimalVar(NumericVar):
    type=Decimal
    step=None
    dummy_value = property(lambda self: self.default_value or Decimal(self.max+self.min)/2)

    @classmethod
    def _roundVolume(self, vol):
        return self.step*round(vol/self.step) if self.step else vol

    def remote_set(self, value, force=False):
        value = self._roundVolume(self.type(value))
        return super().remote_set(value, force)

    def set(self, val):
        super().set(Decimal(val) if isinstance(val, int) else val)


class PresetValueMixin:
    """ Inherit if variable value shall have a preset value. Set value in inherited class. """
    value = None

    def __init__(self,*args,**xargs):
        super().__init__(*args,**xargs)
        self._val = self.value
    def unset(self): self._val = self.value


class ConstantValueMixin(PresetValueMixin):
    """ Inerhit if variable value may not change """
    def matches(self,*args,**xargs): return False
    def set(self,*args,**xargs): pass


class ClientToServerVarMixin:
    """ Inheriting variables are write only on client and read only on server """
    call = None

    # for client
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        if isinstance(self.target, ClientType): self.target.bind(on_connect=lambda:self.on_set())

    def get(self): return "(select)" if isinstance(self.target, ClientType) else super().get()

    def is_set(self):
        return True if isinstance(self.target, ClientType) else super().is_set()

    # for server
    def remote_set(self, *args, **xargs):
        if isinstance(self.target, ClientType): return super().remote_set(*args, **xargs)
        else: raise ValueError("This is a unidirectionally shared variable.")

    def resend(self): pass


class ServerToClientVarMixin:
    options = []

    def remote_set(self, *args, **xargs): raise RuntimeError("Cannot set value!")


class OfflineVarMixin:
    """ Inherit if the value shall not ever be transmitted """

    def matches(self, data): return False
    def remote_set(self, *args, **xargs): raise ValueError("Cannot set value!")
    def async_poll(self, *args, **xargs): pass
    def resend(self, *args, **xargs): pass


class VarBlock:
    """
    A shared variable block returns a list of values when polled on server.
    Handles CVa\r CVb\r CVc\r CVEND on Denon.
    Subvariables must be added to the Scheme as Scheme.shared_var(parent=VarBlock).
    """
    _resending = False

    def resend(self):
        if self._resending: return #prevent recursive call when schedule() polls
        self._resending = True
        def func(*shared_vars):
            for var in shared_vars: self._send(var.serialize(var.get()))
        try: self.target.schedule(func, requires=self.children)
        finally: self._resending = False

    def is_set(self): return True
    def consume(self, *args, **xargs): pass
    def remote_set(self, *args, **xargs): raise ValueError("Cannot set value!")

