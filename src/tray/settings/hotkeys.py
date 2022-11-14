import traceback
from gi.repository import Gdk
from pynput import mouse, keyboard
from ...core.transmission import features
from ..common import GladeGtk, gtk, config


class HotkeysMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        item_hotkeys = self.builder.get_object("hotkeys")
        item_hotkeys.connect("state-set", config.connect_to_object(("hotkeys", "volume_hotkeys"),
            item_hotkeys.get_active, item_hotkeys.set_active))
        self.connect_feature_selector_to_config(
            combobox_id="mouse_gesture_function", config_property=("hotkeys", "mouse", 0, "feature"),
            allow_type=features.NumericFeature, default_value="@volume_id")
        self.connect_feature_selector_to_config(
            combobox_id="keyboard_hotkeys_function", config_property=("hotkeys", "keyboard", 0, "feature"),
            allow_type=features.NumericFeature, default_value="@volume_id")
        self.connect_adjustment_to_config("mouse_sensitivity", ("hotkeys", "mouse", 0, "sensitivity"))
        self.connect_adjustment_to_config("mouse_max_step", ("hotkeys", "mouse", 0, "max_step"))
        self.connect_adjustment_to_config("hotkey_steps", ("hotkeys", "keyboard", 0, "step"))
        self._set_mouse_button_label(self.builder.get_object("mouse_button"),
            config["hotkeys"]["mouse"][0]["button"])

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

    @gtk
    def _set_mouse_button_label(self, widget, value):
        try: label = mouse.Button(value).name
        except:
            traceback.print_exc()
            label = "?"
        widget.set_label(label)
        widget.set_sensitive(True)

    def set_mouse_key(self, key):
        pass



