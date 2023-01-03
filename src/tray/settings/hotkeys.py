import traceback
from gi.repository import Gdk, Gtk
from pynput import mouse, keyboard
from ...core.transmission import features
from ..common import GladeGtk, gtk, config, resolve_feature_id


class _Shortcut:

    def __init__(self, app, i=None):
        self.app = app
        if i is None:
            self.i = len(config["hotkeys"][self.config_property])
            self.conf = self.new_conf.copy()
            config["hotkeys"][self.config_property].append(self.conf)
        else:
            self.conf = config["hotkeys"][self.config_property][i]
            self.i = i
        self.objects = []
        self.build()
        remove = self.attach(Gtk.Button("–"))
        remove.connect("clicked", self.on_remove_clicked)

    def build(self): pass

    def on_remove_clicked(self, *args, **xargs):
        for obj in self.objects: obj.destroy()

    def attach(self, obj):
        obj.show_all()
        grid = self.app.builder.get_object(self.grid_id)
        if self.objects:
            grid.attach_next_to(obj, self.objects[-1], Gtk.PositionType.RIGHT, 1, 1)
        else:
            grid.attach_next_to(obj, None, Gtk.PositionType.BOTTOM, 1, 1)
        self.objects.append(obj)
        return obj


class HotkeySetting(_Shortcut):
    config_property = "keyboard"
    new_conf = {"key": None, "step": 3, "feature": None}
    grid_id = "keyboard_hotkeys"

    def build(self):
        key_selector = self.attach(Gtk.Button())
        self._set_hotkey_label(key_selector, self.conf["key"])
        key_selector.connect("clicked", self.on_hotkey_button_clicked, self.i)
        combobox = self.attach(Gtk.ComboBox())
        self.app.connect_feature_selector_to_config(
            combobox=combobox, config_property=("hotkeys", "keyboard", self.i, "feature"),
            allow_types=(features.NumericFeature, features.BoolFeature), default_value="@volume_id")
        self.spin = self.attach(Gtk.SpinButton())
        self.show_spin()
        combobox.connect("changed", self.show_spin)
        adj = Gtk.Adjustment()
        adj.configure(0, -1000, 1000, .5, 10, .5)
        self.app.connect_adjustment_to_config(adj, ("hotkeys", "keyboard", self.i, "step"))
        self.spin.configure(adj, 0.5, 1)

    def on_remove_clicked(self, *args, **xargs):
        super().on_remove_clicked(*args, **xargs)
        self.conf["key"] = None
        config.save()
        self.app.app_manager.main_app.input_listener.refresh_hotkeys()

    def show_spin(self, w=None):
        f = self.app.target.features.get(resolve_feature_id(self.conf["feature"]))
        if f is not None and f.type != bool: self.spin.show()
        else: self.spin.hide()

    def on_hotkey_button_clicked(self, widget, i):
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
                    config["hotkeys"]["keyboard"][i]["key"] = code
                    config.save()
                    self.app.app_manager.main_app.input_listener.refresh_hotkeys()
            self._set_hotkey_label(widget, config["hotkeys"]["keyboard"][i]["key"])
            done.append(True)

        def on_release(key):
            try: modifiers.remove(listener.canonical(key))
            except (ValueError, KeyError): pass
            if done:
                gtk(Gdk.Seat.ungrab)(seat)
                listener.stop()
                self.app._can_close = True

        modifiers = set()
        done = []
        self.app._can_close = False
        widget.set_label("Press key ...")
        widget.set_sensitive(False)
        seat = Gdk.Display.get_default_seat(self.app.window.get_display())
        Gdk.Seat.grab(seat, self.app.window.get_window(), Gdk.SeatCapabilities.KEYBOARD, False)
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

    @gtk
    def _set_hotkey_label(self, widget, value):
        widget.set_label(str(value))
        widget.set_sensitive(True)


class MouseGesture(_Shortcut):
    config_property = "mouse"
    new_conf = {"button": None, "sensitivity": 60, "max_step": 8, "feature": None}
    grid_id = "mouse_gestures"

    def build(self):
        button = self.attach(Gtk.Button())
        button.connect("clicked", self.on_mouse_button_clicked, self.i)
        self._set_mouse_button_label(button, config["hotkeys"]["mouse"][self.i]["button"])
        function = self.attach(Gtk.ComboBox())
        self.app.connect_feature_selector_to_config(
            combobox=function,
            config_property=("hotkeys", "mouse", self.i, "feature"),
            allow_types=(features.NumericFeature,), default_value="@volume_id")
        sensitivity = self.attach(Gtk.SpinButton())
        adj = Gtk.Adjustment()
        adj.configure(0, 1, 1000, 1, 10, 1)
        sensitivity.set_adjustment(adj)
        self.app.connect_adjustment_to_config(adj, ("hotkeys", "mouse", self.i, "sensitivity"))
        max_step = self.attach(Gtk.SpinButton())
        adj = Gtk.Adjustment()
        adj.configure(0, 0, 100, 1, 10, 1)
        max_step.set_adjustment(adj)
        self.app.connect_adjustment_to_config(max_step, ("hotkeys", "mouse", 0, "max_step"))

    def on_mouse_button_clicked(self, widget, i):
        def on_click(x, y, button, pressed):
            gtk(Gdk.Seat.ungrab)(seat)
            mouse_listener.stop()
            if button.value == 1: print("Button1 is not allowed.")
            else:
                with self.app.app_manager.main_app.input_listener.refresh_mouse():
                    config["hotkeys"]["mouse"][i]["button"] = button.value
                    config.save()
            self._set_mouse_button_label(widget, config["hotkeys"]["mouse"][i]["button"])
        widget.set_label("Press mouse key ...")
        widget.set_sensitive(False)
        seat = Gdk.Display.get_default_seat(self.app.window.get_display())
        Gdk.Seat.grab(seat, self.app.window.get_window(), Gdk.SeatCapabilities.POINTER, False)
        mouse_listener = mouse.Listener(on_click=on_click)
        mouse_listener.start()

    def on_remove_clicked(self, *args, **xargs):
        super().on_remove_clicked(*args, **xargs)
        with self.app.app_manager.main_app.input_listener.refresh_mouse():
            self.conf["button"] = None
            config.save()

    @gtk
    def _set_mouse_button_label(self, widget, value):
        try: label = mouse.Button(value).name
        except:
            traceback.print_exc()
            label = "?"
        widget.set_label(label)
        widget.set_sensitive(True)


class HotkeysMixin:
    _can_close = True

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        config["hotkeys"]["keyboard"] = [e for e in config["hotkeys"]["keyboard"] if e["key"] is not None]
        config["hotkeys"]["mouse"] = [e for e in config["hotkeys"]["mouse"] if e["button"] is not None]
        for i, conf in enumerate(config["hotkeys"]["keyboard"]):
            HotkeySetting(self, i)
        for i, conf in enumerate(config["hotkeys"]["mouse"]):
            MouseGesture(self, i)

    def on_hotkeys_keyboard_add_clicked(self, w):
        HotkeySetting(self)

    def on_mouse_gesture_add_clicked(self, w):
        MouseGesture(self)

    def on_close_click(self, *args, **xargs):
        if self._can_close: return super().on_close_click(*args, **xargs)
        else: return True

