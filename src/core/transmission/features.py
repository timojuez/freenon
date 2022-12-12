import sys, traceback, re, math
from contextlib import suppress
from decimal import Decimal
from threading import Event, Lock, RLock, Timer, Thread
from datetime import datetime, timedelta
from ..util import call_sequence, Bindable, AttrDict
from .types import ClientType, ServerType


MAX_CALL_DELAY = 2 #seconds, max delay for calling function using "@require"


class FunctionCall(object):
    """ Function call that requires features. Drops call if no connection """

    def __init__(self, target, func, args=tuple(), kwargs={}, features=tuple(), timeout=MAX_CALL_DELAY):
        self._lock = Lock()
        self._target = target
        self._func = func
        self._features = features
        self._args = args
        self._kwargs = kwargs
        self._timeout = datetime.now()+timedelta(seconds=timeout) if timeout != None else None
        self.postpone()
        try: [f.async_poll() for f in self._missing_features]
        except ConnectionError: self.cancel()

    def __repr__(self): return "<pending%s>"%self._func

    _missing_features = property(lambda self: list(filter(lambda f:not f.is_set(), self._features)))

    def try_call(self):
        with self._lock:
            if not self.active: return False
            if not self._missing_features:
                try: self._func(*self._features, *self._args, **self._kwargs)
                except ConnectionError: pass
                self.cancel()
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
    
    def on_feature_set(self, feature):
        if feature in self._features and self.try_call():
            if self._target.verbose > 5: print("[%s] called pending function %s"
                %(self.__class__.__name__, self._func.__name__), file=sys.stderr)


class Features(AttrDict):
    
    def wait_for(self, *features):
        try: features = [f if isinstance(f, Feature) else self[f] for f in features]
        except KeyError as e:
            print(f"[{self.__class__.__name__}] Warning: Target does not provide feature. {e}",
                file=sys.stderr)
            return False
        threads = [Thread(target=f.wait_poll, daemon=True, name="wait_for") for f in features]
        for t in threads: t.start()
        for t in threads: t.join()
        return all([f.is_set() for f in features])
        

class FeatureInterface(object):
    name = "Short description"
    category = "Misc"
    call = None # for retrieval, call target.send(call)
    default_value = None # if no response from server
    dummy_value = None # for dummy server
    type = object # value data type, e.g. int, bool, str
    #id = "id" # feature will be available as target.id; default: id = class name

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
        """ transform @value to string """
        raise NotImplementedError()

    def unserialize(self, data):
        """ transform string @data to type self.type """
        raise NotImplementedError()


class _MetaFeature(type):

    def __init__(cls, name, bases, dct):
        if "id" not in dct:
            cls.id = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        if "name" not in dct:
            cls.name = re.sub(r'(?<!^)(?=[A-Z])', ' ', cls.__name__)
            cls.name = " ".join(["%s%s"%(x[0].upper(),x[1:]) if len(x)>0 else "" for x in cls.name.split("_")])

        
class AsyncFeature(FeatureInterface, Bindable, metaclass=_MetaFeature):
    """
    A target attribute for high level communication
    If being used in a with statement, the value will not change during execution of the inside code.
    
    Warning: Calling get() in the event callbacks can cause deadlocks.
        Instead, get the value from the function parameter.
    """
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
        self._lock = self._lock()
        self._event_on_set = self._event_on_set()
        self.children = []
        target.features[self.id] = self
        
    name = property(lambda self:self.__class__.__name__)
    
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

            def __init__(self, *args, **xargs):
                super().__init__(*args, **xargs)
                self.parent = self.target.features[parent.id]
                self.parent.children.append(self.id)

            def matches(self, data):
                return self.parent.matches(data) and super().matches(self.parent.unserialize(data))

            def poll_on_client(self, *args, **xargs):
                self.parent.poll_on_client(*args, **xargs)

            def _send(self, *args, **xargs):
                if issubclass(self.target.__class__, ServerType):
                    self.parent.resend()
                else:
                    super()._send(*args, **xargs)

            def serialize(self, value):
                return self.parent.serialize(super().serialize(value))

            def unserialize(self, data):
                return super().unserialize(self.parent.unserialize(data))
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
        self.target.send(serialized)

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

    def async_poll(self, *args, **xargs): self.target.poll_feature(self, *args, **xargs)
    
    def poll_on_client(self):
        """ async_poll() executed on client side """
        if self.default_value is not None:
            self._timer_set_default = Timer(MAX_CALL_DELAY, self._set_default)
            self._timer_set_default.start()
        if self.call is not None: self.target.send(self.call)
    
    def poll_on_dummy(self):
        if self.dummy_value is not None: val = self.dummy_value
        elif self.default_value is not None: val = self.default_value
        else: raise ValueError("Feature %s has no dummy value."%self.id)
        #self.on_receive_raw_data(f.serialize(val)) # TODO: handle cases where f.call matches but f.matches() is False and maybe f'.matches() is True
        self.set(val)

    def _set_default(self):
        with self._lock:
            if not self.is_set(): self._set(self.default_value)
    
    def resend(self):
        self._send(self.serialize(self.get()))
    
    def consume(self, data):
        """ unserialize and apply @data to this object """
        self.__class__._block_on_remote_set = None # for power.consume("PWON")
        try: d = self.unserialize(data)
        except:
            print(f"Error on {self.id}.consume({repr(data)}):", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        else: return self.target.on_receive_feature_value(self, d)
        
    def set(self, value):
        with self._lock: return self._set(value)
    
    def _set(self, value):
        assert(value is not None)
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
        self.target.on_feature_change(self.id, val)
    
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
            for call in self.target._pending.copy(): # on_feature_set() changes _pending
                call.on_feature_set(self)
        
    def on_unset(self):
        try: self._timer_set_default.cancel()
        except: pass
        self._event_on_set.clear()
    
    def on_processed(self, value):
        """ This event is being called each time the feature is being set to a value
        even if the value is the same as the previous one """
        pass

    def on_send(self):
        """ This event is being fired when a value update has been sent to remote """
        pass


class SynchronousFeature(AsyncFeature):

    def __init__(self,*args,**xargs):
        self._poll_lock = Lock()
        super().__init__(*args,**xargs)

    def get_wait(self):
        with self._poll_lock:
            try: return super().get()
            except ConnectionError:
                if self.wait_poll(): return super().get()
                else: raise ConnectionError("Timeout on waiting for answer for %s"%self.__class__.__name__)

    def wait_poll(self, force=False):
        """ Poll and wait if Feature is unset. Returns False on timeout and True otherwise """
        if not self.target.connected: return False
        if force: self.unset()
        if not self.is_set():
            try: self.async_poll(force)
            except ConnectionError: return False
            if not self._event_on_set.wait(timeout=MAX_CALL_DELAY+.1): return False
        return True


Feature = SynchronousFeature

class NumericFeature(Feature):
    min=0
    max=99


class IntFeature(NumericFeature):
    type=int
    dummy_value = property(lambda self: self.default_value or math.ceil((self.max+self.min)/2))


class SelectFeature(Feature):
    type=str
    options = []
    dummy_value = property(lambda self: self.default_value or (self.options[0] if self.options else "?"))

    def remote_set(self, value, force=False):
        if not force and value not in self.options:
            raise ValueError("Value must be one of %s or try target.features.%s.remote_set(value, force=True)"
                %(self.options, self.id))
        return super().remote_set(value, force)
    

class BoolFeature(SelectFeature):
    type=bool
    options = [True, False]
    dummy_value = property(lambda self: self.default_value or False)


class DecimalFeature(NumericFeature):
    type=Decimal
    dummy_value = property(lambda self: self.default_value or Decimal(self.max+self.min)/2)
    
    def remote_set(self, value, force=False):
        return super().remote_set((Decimal(value) if isinstance(value, int) else value), force)


class PresetValueMixin:
    """ Inherit if feature value shall have a preset value. Set value in inherited class. """
    value = None

    def __init__(self,*args,**xargs):
        super().__init__(*args,**xargs)
        self._val = self.value
    def unset(self): self._val = self.value


class ConstantValueMixin(PresetValueMixin):
    """ Inerhit if feature value may not change """
    def matches(self,*args,**xargs): return False
    def set(self,*args,**xargs): pass


class ClientToServerFeatureMixin:
    """ Inheriting features are write only on client and read only on server """
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
        else: raise ValueError("This is a unidirectional feature")

    def resend(self): isinstance(self.target, ClientType) and super().resend()


class ServerToClientFeatureMixin:
    options = []

    def remote_set(self, *args, **xargs): raise RuntimeError("Cannot set value!")


class MultipartFeatureMixin:
    """ This mixin allows you to send and receive a value in multiple parts. The parts are a
    list. In Telnet, parts could be rows.
    The function serialize() must return a list and unserialize() will be given a list.
    is_complete(l) must return True if l contains all parts """

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._buffer = []

    def is_complete(self, l):
        """ @l list, returns True if l contains all parts and can be unserialized """
        raise NotImplementedError()

    def _send(self, serialized):
        for e in serialized: super()._send(e)

    def consume(self, data):
        self._buffer.append(data)
        if self.is_complete(self._buffer):
            super().consume(self._buffer.copy())
            self._buffer.clear()


class OfflineFeatureMixin:
    """ Inherit if the value shall not ever be transmitted """

    def matches(self, data): return False
    def remote_set(self, *args, **xargs): raise ValueError("Cannot set value!")
    def async_poll(self, *args, **xargs): pass
    def resend(self, *args, **xargs): pass


class FeatureBlock:
    """
    A feature block returns a list of features when polled on server.
    Handles CVa\r CVb\r CVc\r CVEND on Denon.
    Subfeatures must be added to the Scheme as Scheme.add_feature(parent=FeatureBlock).
    """

    def resend(self):
        def func(*features):
            for f in features: self.target.send(f.serialize(f.get()))
        self.target.schedule(func, requires=self.children)

    def is_set(self): return True
    def consume(self, *args, **xargs): pass
    def remote_set(self, *args, **xargs): raise ValueError("Cannot set value!")

