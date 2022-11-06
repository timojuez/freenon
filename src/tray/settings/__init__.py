import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from pynput import mouse, keyboard
from ...core.transmission import features
from ..common import GladeGtk, gtk, config, id_to_string, FeatureSelectorCombobox, FeatureValueCombobox, autostart
from ..setup_wizard import SetupWizard
from .feature_selector_view import FeatureSelectorView


class PowerControlMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        item_poweroffsd = self.builder.get_object("poweroff")
        item_poweroffsd.connect("state-set",
            config.connect_to_object(("power_control", "power_off_on_shutdown"),
            item_poweroffsd.get_active, item_poweroffsd.set_active))
        self.connect_adjustment_to_config("poweroff_delay", ("power_control", "poweroff_after"))


class TrayIconMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.connect_adjustment_to_config("scroll_delta", ("tray", "scroll_delta"))
        self.connect_feature_selector_to_config(
            combobox_id="tray_icon_function", config_property=("tray", "scroll_feature"),
            allow_type=features.NumericFeature, default_value="@volume_id",
            on_changed=lambda *_:self.app_manager.main_app.icon.update_icon())


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
            mouse_listener.stop()
            self._set_mouse_button_label(widget, button.value)
            config["hotkeys"]["mouse"][0]["button"] = button.value
            config.save()
        widget.set_label("Press mouse key ...")
        widget.set_sensitive(False)
        mouse_listener = mouse.Listener(on_click=on_click)
        mouse_listener.start()

    @gtk
    def _set_mouse_button_label(self, widget, value):
        label = mouse.Button(value).name
        widget.set_label(label)
        widget.set_sensitive(True)

    def set_mouse_key(self, key):
        pass


class PopupMenuSettings:

    def __init__(self, *args, on_menu_settings_change=None, **xargs):
        super().__init__(*args, **xargs)
        fs = FeatureSelectorView(self.target, self.builder.get_object("popup_menu_settings"), "Context Menu")
        if on_menu_settings_change: fs.bind(on_change = on_menu_settings_change)
        fs.bind(on_change = config.connect_to_object(["tray", "menu_features"], fs.get_value, fs.set_value))


class NotificationSettings:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.notification_blacklist = nb = FeatureSelectorView(
            self.target, self.builder.get_object("notification_settings"), "Disabled")
        nb.bind(on_change =
            config.connect_to_object(["notifications", "blacklist"], nb.get_value, nb.set_value))


class GeneralMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        checkbox = self.builder.get_object("autostart_checkbox")
        checkbox.set_active(autostart.get_active())
        checkbox.connect("toggled", lambda *_: autostart.set_active(checkbox.get_active()))

    def on_setup_wizard_clicked(self, *args):
        sw = SetupWizard(self.app_manager)
        sw.window.set_transient_for(self.window)
        sw.show()


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

    def connect_feature_selector_to_config(self, combobox_id, config_property, default_value=None,
            *args, on_changed=None, **xargs):
        if default_value:
            xargs["items"] = [("Default – %s"%id_to_string(self.target, default_value), default_value)]
        fc = FeatureSelectorCombobox(self.target, self.builder.get_object(combobox_id), *args, **xargs)
        self._connect_combobox_to_config(config_property, fc, on_changed)

    def connect_value_selector_to_config(self, combobox_id, config_property, *args, on_changed=None, **xargs):
        fc = FeatureValueCombobox(self.target, self.builder.get_object(combobox_id), *args, **xargs)
        self._connect_combobox_to_config(config_property, fc, on_changed)

    def _connect_combobox_to_config(self, config_property, fc, on_changed=None):
        on_changed_ = config.connect_to_object(config_property, fc.get_active, fc.set_active)
        fc.connect("changed", on_changed_)
        if on_changed: fc.connect("changed", on_changed)

    def connect_adjustment_to_config(self, adjustment_id, config_property):
        ad = self.builder.get_object(adjustment_id)
        ad.connect("value-changed", config.connect_to_object(config_property, ad.get_value, ad.set_value))


class Settings(PowerControlMixin, TrayIconMixin, HotkeysMixin, PopupMenuSettings,
    NotificationSettings, GeneralMixin, SettingsBase): pass

