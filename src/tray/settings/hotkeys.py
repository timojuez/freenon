import traceback
from gi.repository import Gdk
from pynput import mouse, keyboard
from ...core.transmission import features
from ..common import GladeGtk, gtk, config


class HotkeysMixin:
    _can_close = True

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.connect_feature_selector_to_config(
            combobox_id="mouse_gesture_function", config_property=("hotkeys", "mouse", 0, "feature"),
            allow_types=(features.NumericFeature,), default_value="@volume_id")
        self.connect_feature_selector_to_config(
            combobox_id="keyboard_hotkeys_function", config_property=("hotkeys", "keyboard", 0, "feature"),
            allow_types=(features.NumericFeature, features.BoolFeature), default_value="@volume_id")
        self.connect_adjustment_to_config("mouse_sensitivity", ("hotkeys", "mouse", 0, "sensitivity"))
        self.connect_adjustment_to_config("mouse_max_step", ("hotkeys", "mouse", 0, "max_step"))
        self.connect_adjustment_to_config("hotkey_steps", ("hotkeys", "keyboard", 0, "step"))
        self._set_mouse_button_label(self.builder.get_object("mouse_button"),
            config["hotkeys"]["mouse"][0]["button"])
        self._set_hotkey_label(self.builder.get_object("hotkey_button"),
            config["hotkeys"]["keyboard"][0]["key"])

    def on_mouse_button_clicked(self, widget):
        def on_click(x, y, button, pressed):
            Gdk.Seat.ungrab(seat)
            mouse_listener.stop()
            if button.value == 1: print("Button1 is not allowed.")
            else:
                config["hotkeys"]["mouse"][0]["button"] = button.value
                config.save()
                self.app_manager.main_app.input_listener.refresh_mouse()
            self._set_mouse_button_label(widget, config["hotkeys"]["mouse"][0]["button"])
        widget.set_label("Press mouse key ...")
        widget.set_sensitive(False)
        seat = Gdk.Display.get_default_seat(self.window.get_display())
        Gdk.Seat.grab(seat, self.window.get_window(), Gdk.SeatCapabilities.POINTER, False)
        mouse_listener = mouse.Listener(on_click=on_click)
        mouse_listener.start()

    def on_hotkey_button_clicked(self, widget):
        def on_press(key):
            key = listener.canonical(key)
            if key == keyboard.Key.esc:
                print("ESC is not allowed.")
            elif key in (keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift):
                modifiers.add(key)
                return
            else:
                tostr = lambda key: key.char if isinstance(key, keyboard.KeyCode) else f"<{key.name}>"
                try: code = "+".join(list(map(tostr, [*modifiers, key])))
                except TypeError: traceback.print_exc()
                else:
                    config["hotkeys"]["keyboard"][0]["key"] = code
                    config.save()
                    self.app_manager.main_app.input_listener.refresh_hotkeys()
            self._set_hotkey_label(widget, config["hotkeys"]["keyboard"][0]["key"])
            done.append(True)

        def on_release(key):
            try: modifiers.remove(listener.canonical(key))
            except (ValueError, KeyError): pass
            if done:
                gtk(Gdk.Seat.ungrab)(seat)
                listener.stop()
                self._can_close = True

        modifiers = set()
        done = []
        self._can_close = False
        widget.set_label("Press key ...")
        widget.set_sensitive(False)
        seat = Gdk.Display.get_default_seat(self.window.get_display())
        Gdk.Seat.grab(seat, self.window.get_window(), Gdk.SeatCapabilities.KEYBOARD, False)
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

    def on_close_click(self, *args, **xargs):
        if self._can_close: return super().on_close_click(*args, **xargs)
        else: return True

    @gtk
    def _set_mouse_button_label(self, widget, value):
        try: label = mouse.Button(value).name
        except:
            traceback.print_exc()
            label = "?"
        widget.set_label(label)
        widget.set_sensitive(True)

    @gtk
    def _set_hotkey_label(self, widget, value):
        widget.set_label(str(value))
        widget.set_sensitive(True)

