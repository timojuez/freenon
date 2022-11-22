import sys
from threading import Thread, Event
from .call_sequence import *
from .function_bind import *


def log_call(func):
    """ object function decorator """
    def call(self,*args,**xargs):
        try: assert(not (self.verbose > 3))
        except:
            print("[%s] %s"%(self.__class__.__name__, func.__name__), file=sys.stderr)
        return func(self,*args,**xargs)
    return call


class AttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

    def copy(self):
        return self.__class__(self)


class AbstractMainloopManager:
    """
    This contains a mainloop which keeps running mainloop_hook() continuously. 
    It can be run in a context ("with") or using start() and stop() or just run mainloop().
    A concrete class should implement mainloop_hook(). The method mainloop_quit() must cause mainloop_hook()
    to exit. Before and after the mainloop, internal functions enter() and exit() are being called.
    """
    _mainloopt = None
    _stoploop = Event

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._stoploop = self._stoploop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def start(self):
        self.enter()
        self._mainloopt = Thread(target=self._mainloop, name=self.__class__.__name__, daemon=True)
        self._mainloopt.start()

    def stop(self):
        self.mainloop_quit()
        self._mainloopt.join()
        self.exit()

    def enter(self):
        """ entering mainloop """
        pass

    def exit(self):
        """ exiting mainloop """
        pass

    def mainloop(self):
        """ listens on server for events and calls on_feature_change. Return when connection closed """
        self.enter()
        try:
            self._mainloop()
        finally:
            self.exit()

    def _mainloop(self):
        """ listens on server for events and calls on_feature_change. Return when connection closed """
        self._stoploop.clear()
        while not self._stoploop.is_set(): self.mainloop_hook()

    def mainloop_hook(self):
        """ This will be called regularly by mainloop """
        pass

    def mainloop_quit(self):
        self._stoploop.set()


