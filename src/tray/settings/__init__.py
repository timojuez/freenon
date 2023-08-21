from gi.repository import Gtk
from ...core.transmission import shared_vars
from ..common import GladeGtk, gtk, config, id_to_string, SharedVarSelectorCombobox, SharedVarValueCombobox, autostart
from ..setup_wizard import SetupWizard
from .shared_var_selector_view import SharedVarSelectorView
from .hotkeys import HotkeysMixin


class PowerControlMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        item_poweroffsd = self.builder.get_object("poweroff")
        item_poweroffsd.connect("state-set",
            config.connect_to_object(("power_control", "power_off_on_shutdown"),
            item_poweroffsd.get_active, item_poweroffsd.set_active))
        self.connect_adjustment_to_config(
            self.builder.get_object("poweroff_delay"), ("power_control", "poweroff_after"))


class TrayIconMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.connect_adjustment_to_config(
            self.builder.get_object("scroll_delta"), ("tray", "scroll_delta"))
        self.connect_var_selector_to_config(
            combobox=self.builder.get_object("tray_icon_function"), config_property=("tray", "scroll_var"),
            allow_types=(shared_vars.NumericVar,), default_value="@volume_id",
            on_changed=lambda *_:self.app_manager.main_app.icon.update_icon())


class PopupMenuSettings:

    def __init__(self, *args, on_menu_settings_change=None, **xargs):
        super().__init__(*args, **xargs)
        vs = SharedVarSelectorView(self.target, self.builder.get_object("popup_menu_settings"), "Context Menu")
        if on_menu_settings_change: vs.bind(on_change = on_menu_settings_change)
        vs.bind(on_change = config.connect_to_object(["tray", "menu_vars"], vs.get_value, vs.set_value))


class NotificationSettings:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.notification_blacklist = nb = SharedVarSelectorView(
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

    def connect_var_selector_to_config(self, combobox, config_property, default_value=None,
            *args, on_changed=None, **xargs):
        if default_value:
            xargs["items"] = [("Default – %s"%id_to_string(self.target, default_value), default_value)]
        fc = SharedVarSelectorCombobox(self.target, combobox, *args, **xargs)
        self._connect_combobox_to_config(config_property, fc, on_changed)

    def connect_value_selector_to_config(self, combobox, config_property, *args, on_changed=None, **xargs):
        fc = SharedVarValueCombobox(self.target, combobox, *args, **xargs)
        self._connect_combobox_to_config(config_property, fc, on_changed)

    def _connect_combobox_to_config(self, config_property, fc, on_changed=None):
        on_changed_ = config.connect_to_object(config_property, fc.get_active, fc.set_active)
        fc.connect("changed", on_changed_)
        if on_changed: fc.connect("changed", on_changed)

    def connect_adjustment_to_config(self, adjustment, config_property):
        adjustment.connect("value-changed",
            config.connect_to_object(config_property, adjustment.get_value, adjustment.set_value))


class Settings(PowerControlMixin, TrayIconMixin, HotkeysMixin, PopupMenuSettings,
    NotificationSettings, GeneralMixin, SettingsBase): pass

