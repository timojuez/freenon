# -*- coding: utf-8 -*-
from contextlib import contextmanager
import time, sys, tempfile, os, traceback
from gi.repository import Gdk
from threading import Thread, Lock, Event
from decimal import Decimal
from contextlib import suppress
from contextlib import AbstractContextManager
from ..info import PKG_NAME
from ..core.util import Bindable
from .common import config, TargetApp, resolve_shared_var_id
from pynput import mouse, keyboard
LINUX = sys.platform == "linux"
if LINUX: from ..core.util.x11_grab import XGrab


def sleep():
    delay = config["hotkeys"]["mouse_delay"]
    if delay: time.sleep(delay/1000)


def get_screen_size(display):
    mon_geoms = [
        display.get_monitor(i).get_geometry()
        for i in range(display.get_n_monitors())
    ]
    x0 = min(r.x            for r in mon_geoms)
    y0 = min(r.y            for r in mon_geoms)
    x1 = max(r.x + r.width  for r in mon_geoms)
    y1 = max(r.y + r.height for r in mon_geoms)
    return x1 - x0, y1 - y0


class KeyBinding(TargetApp):
    """ Mixin class for managing volume up/down hot keys and mouse gesture """
    _mouse_gesture_thread_data = None, None
    _position_ref = None
    _y_ref = None
    _mouse_down_count = 0

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.input_listener = InputDeviceListener()
        self.input_listener.bind(
            on_hotkey_press=self.on_hotkey_press,
            on_mouse_down=self.on_mouse_down,
            on_mouse_up=self.on_mouse_up,
            on_activated_mouse_move=self.on_activated_mouse_move)
        self._shared_var_changed = Event()
        self._mouse_gesture_thread_evt = Event()
        self._set_shared_var_lock = Lock()
        self.target.bind(on_shared_var_change=self.on_gesture_shared_var_change)
        Thread(target=self.mouse_gesture_thread, daemon=True, name="key_binding").start()

    def __enter__(self):
        self.input_listener.__enter__()
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.input_listener.__exit__(*args)

    def on_hotkey_press(self, data):
        if self.verbose >= 5: print(f"[{self.__class__.__name__}] Hotkey pressed:", data)
        def func(var):
            if var.type == bool: var.remote_set(not var.get())
            else: var.remote_set(max(var.min, min(var.max, var.get()+var.type(data["conf"]["step"]))))
        self.target.schedule(func, requires=(data["var_id"],))

    def get_current_gesture_var_id(self):
        if g := self.input_listener.get_current_gesture():
            return g["var_id"]

    def on_gesture_shared_var_change(self, var_id, val):
        """ target's shared var changed """
        if var_id != self.get_current_gesture_var_id(): return
        self._shared_var_changed.set()

    def set_position_reference(self, y, vol):
        """ link a y-coordinate to a shared variable's value """
        if self.verbose >= 6: print(f"[{self.__class__.__name__}] Setting new mouse position reference")
        self._y_ref, self._position_ref = y, vol

    def on_mouse_down(self, gesture, x, y):
        if self.verbose >= 5: print(f"[{self.__class__.__name__}] Gesture activated:", gesture)
        self._mouse_gesture_thread_data = None, None
        this = self._mouse_down_count = (self._mouse_down_count+1)%100
        self._position_ref = None
        def func(var):
            if self._mouse_down_count != this: return # check if this is the most recent call
            self.set_position_reference(y, var.get())
        self.target.schedule(func, requires=(gesture["var_id"],))

    def on_mouse_up(self, gesture, x, y):
        self._shared_var_changed.set() # break _shared_var_changed.wait()

    def on_activated_mouse_move(self, gesture, x, y):
        if (var := self.target.shared_vars.get(gesture["var_id"])) is None: return
        if self._position_ref is None: return
        screen_height = get_screen_size(Gdk.Display.get_default())[1]
        new_value = self._position_ref-var.type((y-self._y_ref)/screen_height*gesture["conf"]["sensitivity"])
        if self._mouse_gesture_thread_data == (new_value, gesture): return
        max_step = Decimal(gesture["conf"]["max_step"])
        try: max_ = var.get()+max_step
        except ConnectionError: return
        if self.verbose >= 1 and new_value > max_:
            print(f"[{self.__class__.__name__}] "
                f"Mouse gesture: New value {new_value} exceeds max step ({max_step})", file=sys.stderr)
        max_ = min(var.max, max_)
        min_ = var.min
        if new_value > max_ or new_value < min_:
            # mouse has been moved to an illegal point
            new_value = max(min_, min(max_, new_value))
            self.set_position_reference(y, new_value)
        if self._mouse_gesture_thread_data == (new_value, gesture): return
        with self._set_shared_var_lock:
            self._mouse_gesture_thread_data = new_value, gesture
            self._mouse_gesture_thread_evt.set()

    def mouse_gesture_thread(self):
        while True:
            self._mouse_gesture_thread_evt.wait()
            with self._set_shared_var_lock:
                self._mouse_gesture_thread_evt.clear()
                new_value, gesture = self._mouse_gesture_thread_data
            if var := self.target.shared_vars.get(gesture["var_id"]):
                try: self._update_shared_var_value(var, new_value)
                except ConnectionError: pass

    def _update_shared_var_value(self, var, new_value):
        if new_value in (None, var.get()): return
        self._shared_var_changed.clear()
        try: var.remote_set(new_value)
        except: traceback.print_exc()
        sleep()
        self._shared_var_changed.wait(.2) # wait for on_shared_var_change


class InputDeviceListener(Bindable, AbstractContextManager):
    """ Runs the pynput listeners """

    def __init__(self):
        super().__init__()
        self._buttons = []

    def __enter__(self):
        self.mouse_listener = mouse.Listener(
            on_click=self.on_mouse_click,
            on_move=self.on_mouse_move,
        )
        self._start_hotkey_listener()
        if LINUX: self._xgrab = XGrab()
        self._controller = keyboard.Controller()
        self.mouse_listener.start()
        self.set_button_grabbing(True)
        if LINUX: self._xgrab.enter()
        return super().__enter__()

    def __exit__(self, *args, **xargs):
        super().__exit__(*args, **xargs)
        self.mouse_listener.stop()
        try: self.hotkey_listener.stop()
        except: pass
        self.set_button_grabbing(False)
        if LINUX: self._xgrab.exit()

    def get_current_gesture(self):
        gestures = [e for e in config["hotkeys"]["mouse"] if e["button"] in self._buttons]
        if gestures:
            conf = gestures[0]
            return {"conf": conf, "var_id": resolve_shared_var_id(conf["var"])}

    def on_mouse_click(self, x, y, button, pressed):
        if pressed: self._buttons.append(button.value)
        else: self._buttons.remove(button.value)
        if gesture := self.get_current_gesture():
            if pressed: self.on_mouse_down(gesture, x, y)
            else: self.on_mouse_up(gesture, x, y)

    def on_mouse_down(self, gesture, x, y): pass
    def on_mouse_up(self, gesture, x, y): pass

    def on_mouse_move(self, x, y):
        if gesture := self.get_current_gesture():
            self.on_activated_mouse_move(gesture, x, y)

    def on_activated_mouse_move(self, gesture, x, y): pass

    def set_key_grabbing(self, value):
        """ stop forwarding volume media buttons to other programs """
        if not LINUX: return
        for key in [keyboard.Key.media_volume_up, keyboard.Key.media_volume_up, keyboard.Key.media_volume_mute]:
            if value: self._xgrab.grab_key(key.value.vk, "Control")
            else: self._xgrab.ungrab_key(key.value.vk)

    def refresh_hotkeys(self):
        try: self.hotkey_listener.stop()
        except: pass
        self._start_hotkey_listener()

    def on_hotkey_press(self, data): pass

    def _start_hotkey_listener(self):
        fire = lambda ks: self.on_hotkey_press({"var_id": resolve_shared_var_id(ks["var"]), "conf": ks})
        try: self.hotkey_listener = keyboard.GlobalHotKeys(
            {ks["key"]: lambda ks=ks: fire(ks) for ks in config["hotkeys"]["keyboard"] if ks["key"]})
        except ValueError: traceback.print_exc()
        else: self.hotkey_listener.start()

    @contextmanager
    def refresh_mouse(self):
        self.set_button_grabbing(False)
        yield
        self.set_button_grabbing(True)

    def set_button_grabbing(self, value):
        """ stop forwarding configured mouse button events to other programs """
        if not LINUX: return
        buttons = [e["button"] for e in config["hotkeys"]["mouse"]]
        try:
            for b in buttons:
                if b is None: continue
                if value:
                    self._xgrab.grab_button(b)
                else:
                    self._xgrab.ungrab_button(b)
        except: traceback.print_exc()

