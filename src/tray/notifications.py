from gi.repository import Gtk
import sys
from threading import Timer
from ..core import features
from .common import config, resolve_feature_id, gtk, GladeGtk, APP_NAME, Singleton, TargetApp, NotificationBase, Notification
from .tray import TrayMixin
from .key_binding import KeyBinding
from .power_control import PowerControlMixin


class GaugeNotification(GladeGtk, NotificationBase, metaclass=Singleton):
    GLADE = "../share/gauge_notification.glade"
    _timeout = 2
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._position()
        self.level = self.builder.get_object("level")
        self.title = self.builder.get_object("title")
        self.subtitle = self.builder.get_object("subtitle")
        self.window = self.builder.get_object("window")
        self.width, self.height = self.window.get_size()
    
    def set_timeout(self, t): self._timeout = t/1000
    
    def on_click(self, *args): self.hide()
    
    @gtk
    def update(self, title, message, value, min, max):
        if not (min <= value <= max):
            return sys.stderr.write(f"[{self.__class__.__name__}] WARNING: "
                f"Value out of bounds: {value}. title='{title}', message='{message}'.\n")
        diff = max-min
        value_normalised = (value-min)/diff
        self.title.set_text(title)
        self.subtitle.set_text(message)
        self.level.set_value(value_normalised*100)

    @gtk
    def _position(self):
        self.window.move(self.window.get_screen().get_width()-self.width-50, 170)

    def show(self):
        super().show()
        try: self._timer.cancel()
        except: pass
        self._timer = Timer(self._timeout, self.hide)
        self._timer.start()


class FeatureNotification:

    def __init__(self, feature, *args, **xargs):
        super().__init__(*args, **xargs)
        self.f = feature
        self.target = feature.target


class TextNotification(FeatureNotification, Notification):
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.set_urgency(2)
        self.set_timeout(config["notifications"]["timeout"])
        self.target.preload_features.add("name")

    def show(self): self.target.schedule(self._show, requires=("name",))

    def _show(self, name):
        try:
            val = {True:"On",False:"Off"}.get(self.f.get(), self.f.get())
            self.update(f"{self.f.name}: {val}", name.get())
        except ConnectionError:
            self.update("Connecting ...", name.get())
        super().show()


class NumericNotification(FeatureNotification):
    
    def __init__(self, scale_popup, *args, **xargs):
        super().__init__(*args, **xargs)
        self.scale_popup = scale_popup
        self._n = GaugeNotification()
        self._n.set_timeout(config["notifications"]["timeout"])

    def show(self):
        if self.scale_popup._current_feature == self.f and self.scale_popup.visible: return
        try: value = self.f.get()
        except ConnectionError: value = self.f.min
        self._n.update(
            title=self.f.name,
            message=str(self.f),
            value=value,
            min=self.f.min,
            max=self.f.max)
        self._n.show()

    def hide(self): self._n.hide()


class NotificationMixin(TrayMixin, KeyBinding, PowerControlMixin, TargetApp):
    """ Does the graphical notifications """

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._notifications = {f.id: self.create_notification(f) for f in self.target.features.values()}
        self.target.bind(on_feature_change = self.show_notification_on_feature_change)
        self._poweron_n2 = Notification(
            buttons=[
                ("Cancel", lambda:None),
                ("OK", self.poweron)],
            timeout_action=self.poweron)
        self._poweron_n2.set_timeout(config["power_control"]["poweron_notification_timeout"]*1000)
        self._power_notifications.append(self._poweron_n2)

    def create_notification(self, f):
        if isinstance(f, features.NumericFeature): return NumericNotification(self.scale_popup, f)
        if isinstance(f, features.SelectFeature): return TextNotification(f,
            default_click_action=lambda *_: self.on_notification_clicked(f))

    def on_notification_clicked(self, f):
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Disable notifications for '{f.name}'?",
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.settings.notification_blacklist.add_item(f.id)
        dialog.destroy()

    def show_notification(self, f_id):
        if f_id not in [resolve_feature_id(f_id) for f_id in config["notifications"]["blacklist"]]:
            if n := self._notifications.get(f_id): n.show()

    def on_mouse_down(self,*args,**xargs):
        def notify(name, power=None):
            if power and power.get() == False:
                self._poweron_n2.update("Power on %s"%name.get())
                self._poweron_n2.show()
            else: self.show_notification(config.gesture_feature)
        requires = ["name"]
        if config.power in self.target.features: requires.append(config.power)
        self.target.schedule(notify, requires=requires)
        super().on_mouse_down(*args,**xargs)

    def on_target_power_change(self, power):
        super().on_target_power_change(power)
        if power == True:
            self._poweron_n2.close()

    def on_volume_key_press(self,*args,**xargs):
        self.show_notification(config.hotkeys_feature)
        super().on_volume_key_press(*args,**xargs)

    def show_notification_on_feature_change(self, f_id, value): # bound to target
        f = self.target.features[f_id]
        if f._prev_val is not None and f.isset(): self.show_notification(f_id)

    def on_scroll_up(self, *args, **xargs):
        self.show_notification(config.tray_feature)
        super().on_scroll_up(*args,**xargs)
        
    def on_scroll_down(self, *args, **xargs):
        self.show_notification(config.tray_feature)
        super().on_scroll_down(*args,**xargs)

