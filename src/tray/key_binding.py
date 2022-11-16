# -*- coding: utf-8 -*-
import time, sys, tempfile, os, traceback
from threading import Thread, Lock, Event
from decimal import Decimal
from contextlib import suppress
from contextlib import AbstractContextManager
from ..info import PKG_NAME
from ..core.util import Bindable
from .common import config, TargetApp
from pynput import mouse, keyboard
LINUX = sys.platform == "linux"
if LINUX: from ..core.util.x11_grab import XGrab


def sleep():
    delay = config["hotkeys"]["mouse_delay"]
    if delay: time.sleep(delay/1000)


class KeyBinding(TargetApp):
    """ Mixin class for managing volume up/down hot keys and mouse gesture """
    _new_value = None
    _position_ref = None
    _y_ref = None
    _mouse_down_count = 0

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.input_listener = InputDeviceListener()
        self.input_listener.bind(
            on_mouse_down=self.on_mouse_down,
            on_mouse_up=self.on_mouse_up,
            on_activated_mouse_move=self.on_activated_mouse_move,
            on_volume_key_press=self.on_volume_key_press,
            on_mute_key_press=self.on_mute_key_press)
        self._feature_changed = Event()
        self._feature_step = Event()
        self._set_feature_lock = Lock()
        self.target.preload_features.add(config.hotkeys_feature)
        self.target.preload_features.add(config.gesture_feature)
        self.target.bind(on_feature_change=self.on_gesture_feature_change)
        Thread(target=self.mouse_gesture_thread, daemon=True, name="key_binding").start()

    def __enter__(self):
        self.input_listener.__enter__()
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.input_listener.__exit__(*args)

    def on_gesture_feature_change(self, f_id, val):
        """ target feature changed """
        if f_id != config.gesture_feature: return
        self._feature_changed.set()

    def set_position_reference(self, y, vol):
        """ link a y-coordinate to a feature value """
        self._y_ref, self._position_ref = y, vol

    def on_mouse_down(self, x, y):
        self._new_value = None
        this = self._mouse_down_count = (self._mouse_down_count+1)%100
        self._position_ref = None
        def func(f):
            if self._mouse_down_count != this: return # check if this is the most recent call
            self.set_position_reference(y, f.get())
        self.target.schedule(func, requires=(config.gesture_feature,))

    def on_mouse_up(self, x, y):
        self._feature_changed.set() # break _feature_changed.wait()

    def on_activated_mouse_move(self, x, y):
        f = self.target.features.get(config.gesture_feature)
        if f and self._position_ref is not None:
            try:
                new_value = self._position_ref-int((y-self._y_ref)*config["hotkeys"]["mouse"][0]["sensitivity"])
                max_ = min(f.max, f.get()+Decimal(config["hotkeys"]["mouse"][0]["max_step"]))
                min_ = f.min
                if new_value > max_ or new_value < min_:
                    # mouse has been moved to an illegal point
                    new_value = max(min_, min(max_, new_value))
                    self.set_position_reference(y, new_value)
                self.set_feature_value(new_value)
            except ConnectionError: pass

    def set_feature_value(self, value):
        with self._set_feature_lock:
            self._new_value = value
            self._feature_step.set()

    def on_volume_key_press(self, button):
        self._save_set_feature_to_relative_value(
            config.hotkeys_feature, Decimal(config["hotkeys"]["keyboard"][0]["step"])*(int(button)*2-1))

    def on_mute_key_press(self):
        self.target.schedule(lambda muted: muted.remote_set(not muted.get()), requires=(config.muted,))

    def mouse_gesture_thread(self):
        while True:
            self._feature_step.wait()
            if f := self.target.features.get(config.gesture_feature):
                try: self._update_feature_value(f)
                except ConnectionError: pass

    def _update_feature_value(self, f):
        with self._set_feature_lock:
            self._feature_step.clear()
            new_value = self._new_value
        if new_value in (None, f.get()): return
        self._feature_changed.clear()
        f.remote_set(new_value)
        sleep()
        self._feature_changed.wait(.2) # wait for on_feature_change


class InputDeviceListener(Bindable, AbstractContextManager):
    """ Runs the pynput listeners """
    _pressed = False
    
    def __enter__(self):
        self._ctrl = False
        self.mouse_listener = mouse.Listener(
            on_click=self.on_mouse_click,
            on_move=self.on_mouse_move,
        )
        self.key_listener = keyboard.Listener(
            on_press=self.on_hotkey_press,
            on_release=self.on_hotkey_release,
        )
        if LINUX: self._xgrab = XGrab()
        self._controller = keyboard.Controller()
        self._config_button = config["hotkeys"]["mouse"][0]["button"]
        self.mouse_listener.start()
        self.key_listener.start()
        self.set_key_grabbing(config["hotkeys"]["volume_hotkeys"])
        self.set_button_grabbing(bool(self._config_button))
        if LINUX: self._xgrab.enter()
        return super().__enter__()

    def __exit__(self, *args, **xargs):
        super().__exit__(*args, **xargs)
        self.mouse_listener.stop()
        self.key_listener.stop()
        self.set_key_grabbing(False)
        self.set_button_grabbing(False)
        if LINUX: self._xgrab.exit()

    def on_mouse_click(self, x, y, button, pressed):
        if button.value != self._config_button: return
        self._pressed = pressed
        if pressed: self.on_mouse_down(x, y)
        else: self.on_mouse_up(x, y)

    def on_mouse_down(self, x, y): pass
    def on_mouse_up(self, x, y): pass

    def on_mouse_move(self, x, y):
        if self._pressed: self.on_activated_mouse_move(x, y)

    def on_activated_mouse_move(self, x, y): pass

    def on_hotkey_press(self, key):
        if not config["hotkeys"]["volume_hotkeys"]: return
        key = self.key_listener.canonical(key)
        if key == keyboard.Key.ctrl: self._ctrl = True
        elif not self._ctrl: return
        elif key == keyboard.Key.media_volume_up: self.on_volume_key_press(True)
        elif key == keyboard.Key.media_volume_down: self.on_volume_key_press(False)
        elif key == keyboard.Key.media_volume_mute: self.on_mute_key_press()

    def on_volume_key_press(self, pressed): pass
    def on_mute_key_press(self): pass

    def on_hotkey_release(self, key):
        key = self.key_listener.canonical(key)
        if key == keyboard.Key.ctrl: self._ctrl = False

    def set_keyboard_media_keys(self, *args, **xargs):
        self.set_key_grabbing(False)
        super().set_keyboard_media_keys(*args, **xargs)
        self.set_key_grabbing(config["hotkeys"]["volume_hotkeys"])

    def set_key_grabbing(self, value):
        """ stop forwarding volume media buttons to other programs """
        if not LINUX: return
        for key in [keyboard.Key.media_volume_up, keyboard.Key.media_volume_up, keyboard.Key.media_volume_mute]:
            if value: self._xgrab.grab_key(key.value.vk, "Control")
            else: self._xgrab.ungrab_key(key.value.vk)

    def refresh_mouse(self):
        self.set_button_grabbing(False)
        self._config_button = config["hotkeys"]["mouse"][0]["button"]
        self.set_button_grabbing(bool(self._config_button))

    def set_button_grabbing(self, value):
        """ stop forwarding configured mouse button events to other programs """
        if not LINUX or not self._config_button: return
        try:
            if value: self._xgrab.grab_button(self._config_button)
            else: self._xgrab.ungrab_button(self._config_button)
        except: traceback.print_exc()

