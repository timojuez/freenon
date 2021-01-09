import gi
gi.require_version("Gtk", "3.0")
gi.require_version('Notify', '0.7')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import GLib, Gtk, Gdk, Notify, AppIndicator3, GdkPixbuf, Gio
import sys, pkgutil
from threading import Timer
from ..util.async_widget import bind_widget_to_value
from ..amp import features
from ..common.config import config
from ..util.function_bind import Bindable
from .. import NAME, AUTHOR, URL, VERSION, COPYRIGHT


Notify.init(NAME)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def gtk(func):
    return lambda *args,**xargs: GLib.idle_add(lambda:func(*args,**xargs))


class _Icon(Bindable):

    def set_icon(self, icon, help):
        """ @icon binary """
        with open(self._icon_path,"wb") as fp: icon.save(fp, "PNG")
        self.set_icon_by_path(self._icon_path, help)
        

class _Notification(Bindable):

    def set_urgency(self, n): pass


class GUI_Backend:

    def mainloop(self): Gtk.main()
    
    @classmethod
    def exit(self): Gtk.main_quit()


class GladeGtk(metaclass=Singleton):
    GLADE = ""
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.builder = Gtk.Builder()
        self.builder.add_from_string(pkgutil.get_data(__name__, self.GLADE).decode())
        self.builder.connect_signals(self)

    @gtk
    def show(self): self.window.show()

    @gtk
    def hide(self): self.window.hide()


class GaugeNotification(GladeGtk, _Notification):
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
        assert(min <= value <= max)
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


class VolumePopup(GladeGtk):
    GLADE = "../share/volume_popup.glade"
    
    def __init__(self, amp, *args, **xargs):
        super().__init__(*args, **xargs)
        self.amp = amp
        self._current_feature = None

        self.window = self.builder.get_object("window")
        self.width, self.height = self.window.get_size()
        self.scale = self.builder.get_object("scale")
        self.label = self.builder.get_object("label")
        self.title = self.builder.get_object("title")
        self.image = self.builder.get_object("image")
        self.adj = self.builder.get_object("adjustment")
        self.adj.set_page_increment(config.getdecimal("GUI","tray_scroll_delta"))
        
        for f in self.amp.features.values(): f.register_observer(
            lambda *args, f=f, **xargs: f==self._current_feature and gtk(self.on_value_change)(*args,**xargs))

    def set_value(self, value):
        self.scale.set_value(value)
        self.label.set_text("%0.1f"%value)
        
    @gtk
    def set_image(self, path):
        self.image.set_from_file(path)
        
    def on_change(self, event): self.on_widget_change()
    
    def on_focus_out(self, *args): self.hide()
    
    @property
    def visible(self): return self.window.get_visible()
    
    @gtk
    def show(self, f):
        self.on_value_change, self.on_widget_change = bind_widget_to_value(
            f.get, f.set, self.scale.get_value,
            lambda value: f==self._current_feature and self.set_value(value))
        self.title.set_text(f.name)
        self.adj.set_lower(f.min)
        self.adj.set_upper(f.max)
        self._current_feature = f
        self.on_value_change()
        super().show()


class Notification(_Notification, Notify.Notification):

    def show(self, *args, **xargs):
        try: return super().show(*args,**xargs)
        except GLib.Error as e: print(repr(e), file=sys.stderr)


class MenuMixin:

    def build_menu(self):
        menu = Gtk.Menu()

        for key in config.getlist("GUI","tray_menu_features"):
            key = config.get("Amp", key[1:]) if key.startswith("@") else key
            f = getattr(self.amp.features, key, None)
            if f: menu.append(self.add_feature(f, False))
            if f: self.amp.preload_features.add(key)

        item_more = Gtk.MenuItem("Options")
        submenu = Gtk.Menu()
        submenus = {f.category: Gtk.Menu() for f in self.amp.features.values()}
        for category, menu_ in submenus.items():
            item = Gtk.MenuItem(category)
            submenu.append(item)
            item.set_submenu(menu_)
        for key, f in self.amp.features.items():
            try: submenus[f.category].append(self.add_feature(f, True))
            except RuntimeError: pass
        def poll_all():
            try:
                for f in self.amp.features.values(): f.async_poll()
            except ConnectionError: pass
        self.amp.bind(on_connect=lambda:Timer(1, poll_all).start())
        item_more.set_submenu(submenu)
        menu.append(item_more)

        menu.append(Gtk.SeparatorMenuItem())

        item_poweron = Gtk.CheckMenuItem("Auto power on")
        item_poweron.set_active(self.config["control_power_on"])
        item_poweron.connect("toggled", lambda *args:
            self.config.__setitem__("control_power_on",item_poweron.get_active()))
        menu.append(item_poweron)

        item_poweroff = Gtk.CheckMenuItem("Auto power off")
        item_poweroff.set_active(self.config["control_power_off"])
        item_poweroff.connect("toggled", lambda *args:
            self.config.__setitem__("control_power_off",item_poweroff.get_active()))
        menu.append(item_poweroff)

        menu.append(Gtk.SeparatorMenuItem())

        item_about = Gtk.MenuItem('About %s'%NAME)
        item_about.connect('activate', lambda *args: self.build_about_dialog())
        menu.append(item_about)

        item_quit = Gtk.MenuItem('Quit')
        item_quit.connect('activate', lambda *args: (self.amp.exit(), GUI_Backend.exit()))
        menu.append(item_quit)

        menu.show_all()
        return menu
    
    def add_feature(self, f, show_name=True):
        if isinstance(f, features.BoolFeature): item = self._add_bool_feature(f, show_name)
        elif isinstance(f, features.NumericFeature): item = self._add_numeric_feature(f, show_name)
        elif isinstance(f, features.SelectFeature): item = self._add_select_feature(f, show_name)
        else: raise RuntimeError("Unsupported feature type: %s"%f.type)
        item.set_no_show_all(True)
        f.register_observer(on_set = gtk(item.show))
        f.register_observer(on_unset = gtk(item.hide))
        return item

    def _add_bool_feature(self, f, show_name):
        item = Gtk.CheckMenuItem(f.name)
        on_value_change, on_widget_change = bind_widget_to_value(
            f.get, f.set, item.get_active, item.set_active)
        f.register_observer(gtk(on_value_change))
        item.connect("toggled", lambda event:on_widget_change())
        return item

    def _add_numeric_feature(self, f, show_name):
        item = Gtk.MenuItem(f.name)
        def set(value): item.set_label(f"{f.name}: {value}")
        f.register_observer(gtk(set))
        item.connect("activate", lambda event:self.popup.show(f))
        return item

    def _add_select_feature(self, f, show_name):
        main_item = Gtk.MenuItem(f.name)
        if not show_name: f.register_observer(gtk(main_item.set_label))
        submenu = Gtk.Menu()
        def update_options(*args):
            for c in submenu.get_children(): submenu.remove(c)
            if not show_name:
                submenu.append(Gtk.MenuItem(f.name, sensitive=False))
                submenu.append(Gtk.SeparatorMenuItem())
            f_get = f.get()
            if f.options:
                for o in f.options:
                    item = Gtk.RadioMenuItem(o)
                    item.set_active(f_get == o)
                    item.connect("activate", lambda event, o=o: f.set(o))
                    submenu.append(item)
            else: submenu.append(Gtk.MenuItem(f_get, sensitive=False))
            submenu.show_all()
        f.register_observer(gtk(update_options))
        main_item.set_submenu(submenu)
        return main_item


class Tray(MenuMixin):
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.icon = AppIndicator3.Indicator.new(NAME, NAME, AppIndicator3.IndicatorCategory.HARDWARE)
        self.popup = VolumePopup(self.amp)
        self.icon.connect("scroll-event", self.on_scroll)
        self.icon.set_menu(self.build_menu())
        
    def on_scroll_up(self, steps): pass
    
    def on_scroll_down(self, steps): pass
    
    def build_about_dialog(self):
        ad = Gtk.AboutDialog()
        ad.set_program_name(NAME)
        ad.set_version(VERSION)
        logo = pkgutil.get_data(__name__, "../share/icons/scalable/logo.svg")
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream(Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(logo)), None)
        ad.set_logo(pixbuf)
        ad.set_copyright(COPYRIGHT)
        ad.set_website(URL)
        ad.connect("response", lambda *args: ad.destroy())
        ad.show()
        return ad
        
    def on_scroll(self, icon, steps, direction):
        if direction == Gdk.ScrollDirection.UP: self.on_scroll_up(steps)
        elif direction == Gdk.ScrollDirection.DOWN: self.on_scroll_down(steps)
    
    @gtk
    def show(self): self.icon.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    
    @gtk
    def hide(self): self.icon.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
    
    @gtk
    def set_icon(self, *args): self.icon.set_icon_full(*args)
    

css = b'''
window.dark { background-color: #2e2e2e; }
label.dark { color: #ded6d6; font-weight: bold }
'''
screen = Gdk.Screen.get_default()
css_provider = Gtk.CssProvider()
css_provider.load_from_data(css)
context = Gtk.StyleContext()
context.add_provider_for_screen(screen, css_provider,
                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


