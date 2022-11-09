"""
Connects system events to a target. Can do automatic reconnects and bind computer power to device power.
Main class: TargetController
"""

from .util.system_events import SystemEvents
from .util import log_call


class _Base(SystemEvents):

    def __init__(self, target, *args, **xargs):
        self.verbose = xargs.get("verbose",0)
        self.target = target
        super().__init__(*args, **xargs)

    def poweron(self): pass

    def poweroff(self): pass


class AutoConnect(_Base):
    """ keep target connected whenever possible """

    @log_call
    def on_sigterm(self, sig, frame):
        """ when shutting down computer """
        self.target.stop()
        super().on_sigterm(sig, frame)
        
    @log_call
    def on_suspend(self):
        super().on_suspend()
        self.target.stop()

    @log_call
    def on_resume(self):
        """ Is being executed after resume computer from suspension """
        self.target.start()
        super().on_resume()


class AutoPower(AutoConnect, _Base):
    """ Power off target when computer shuts down or suspends """

    def on_sigterm(self, sig, frame):
        """ when shutting down computer """
        self.poweroff()
        super().on_sigterm(sig, frame)
        
    def on_suspend(self):
        self.poweroff()
        super().on_suspend()


class SoundMixin:
    """ calls on_start_playing and on_stop_playing when pulse decides.
    This mixin causes on_start_playing() to be called when necessary after a reconnection """
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.target.bind(on_connect=self.on_target_connect)

    @log_call
    def on_start_playing(self): pass

    @log_call
    def on_stop_playing(self): pass

    def on_target_connect(self):
        if hasattr(self,"pulse") and self.pulse.connected and self.pulse.is_playing:
            self.on_start_playing()


class TargetController(SoundMixin, AutoPower, AutoConnect, _Base):
    """
    Adds system events listener. Keep target connected whenever possible
    Features: Auto power, auto reconnecting, 
    """
    pass

