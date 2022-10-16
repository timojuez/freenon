import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject
from ...core.transmission import features
from ..common import GladeGtk, gtk, config, id_to_string
from .popup_menu_settings import PopupMenuSettings
from .target_setup import TargetSetup


class FeatureCombobox:

    def __init__(self, target, combobox, allow_type=features.Feature, default_value=None):
        self.c = combobox
        self.target = target
        self.store = Gtk.TreeStore(str, GObject.TYPE_PYOBJECT)
        if default_value:
            self.store.append(None, ["Default – %s"%id_to_string(self.target, default_value), default_value])
        if self.target:
            features_ = [f for f in self.target.features.values() if isinstance(f, allow_type)]
            categories = {f.category:0 for f in features_}
            category = {c:self.store.append(None, [c, None]) for c in categories}
            for f in features_: self.store.append(category[f.category], [f.name, f.id])
        self.c.set_model(self.store)
        renderer_text = Gtk.CellRendererText()
        self.c.pack_start(renderer_text, expand=True)
        self.c.add_attribute(renderer_text, "text", column=0)

    def get_active(self):
        return self.store.get_value(self.c.get_active_iter(), 1)

    def set_active(self, value):
        def iterate(store, path, it):
            v = store.get_value(it, 1)
            if v == value:
                self.c.set_active_iter(it)
        self.c.set_active(-1)
        self.store.foreach(iterate)

    def connect(self, name, cb):
        decorated = lambda *args: cb(*tuple([self if arg == self.c else arg for arg in args]))
        return self.c.connect(name, decorated)

    def __getattr__(self, name): return getattr(self.c, name)


class TrayIconMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.scroll_delta = self.builder.get_object("scroll_delta")
        self.scroll_delta.set_value(config["tray"]["scroll_delta"])
        tray_combobox = FeatureCombobox(
            self.target, self.builder.get_object("tray_icon_function"), features.NumericFeature, "@volume_id")
        tray_combobox.set_active(config["tray"]["scroll_feature"])
        tray_combobox.connect("changed", self.on_tray_icon_function_changed)

    def on_tray_icon_function_changed(self, combobox):
        config["tray"]["scroll_feature"] = combobox.get_active()
        config.save()
        if self.app_manager.main_app: self.app_manager.main_app.icon.update_icon()

    def on_scroll_delta_value_changed(self, *args, **xargs):
        config["tray"]["scroll_delta"] = self.scroll_delta.get_value()
        config.save()


class HotkeysMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        item_poweroffsd = self.builder.get_object("poweroff")
        item_poweroffsd.set_active(config["power_control"]["control_power_off"])
        item_poweroffsd.connect("state-set", lambda *args:
            [config["power_control"].__setitem__("control_power_off",item_poweroffsd.get_active()), config.save()])
        item_hotkeys = self.builder.get_object("hotkeys")
        item_hotkeys.set_active(config["hotkeys"]["volume_hotkeys"])
        item_hotkeys.connect("state-set", lambda *args:
            self.set_keyboard_media_keys(item_hotkeys.get_active()))
        mouse_gesture_function = FeatureCombobox(
            self.target, self.builder.get_object("mouse_gesture_function"),
            features.NumericFeature, "@volume_id")
        mouse_gesture_function.set_active(config["hotkeys"]["mouse_feature"])
        mouse_gesture_function.connect("changed", self.on_mouse_gesture_function_changed)

    def on_mouse_gesture_function_changed(self, combobox):
        config["hotkeys"]["mouse_feature"] = combobox.get_active()
        config.save()

    def set_keyboard_media_keys(self, active):
        config["hotkeys"].__setitem__("volume_hotkeys", active)
        config.save()

    def set_mouse_key(self, key):
        pass


class SettingsBase(GladeGtk):
    GLADE = "../share/settings.glade"

    def __init__(self, app_manager, target, *args, first_run=False, **xargs):
        super().__init__(*args, **xargs)
        self._first_run = first_run
        self.app_manager = app_manager
        self.target = target
        self.window = self.builder.get_object("window")

    def on_close_click(self, *args, **xargs):
        if self._first_run: self.app_manager.main_quit()
        else: self.hide()
        return True


class Settings(TrayIconMixin, HotkeysMixin, TargetSetup, PopupMenuSettings, SettingsBase): pass

