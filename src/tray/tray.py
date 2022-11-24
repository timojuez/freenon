import gi
gi.require_version('AppIndicator3', '0.1')
from gi.repository import GLib, Gtk, Gdk, AppIndicator3, GdkPixbuf, Gio
import sys, math, pkgutil, os, tempfile
from threading import Timer
from decimal import Decimal
from ..core import features
from ..core.util import Bindable
from ..core.util.async_widget import bind_widget_to_value
from ..info import NAME, AUTHOR, URL, VERSION, COPYRIGHT
from .common import gtk, GladeGtk, config, APP_NAME, TargetApp, HideOnUnfocusMixin
from .settings import Settings


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


class ScalePopup(HideOnUnfocusMixin, GladeGtk):
    GLADE = "../share/scale_popup.glade"
    
    def __init__(self, target, *args, **xargs):
        super().__init__(*args, **xargs)
        self.target = target
        self._current_feature = None

        self.window = self.builder.get_object("window")
        self.width, self.height = self.window.get_size()
        self.scale = self.builder.get_object("scale")
        self.label = self.builder.get_object("label")
        self.title = self.builder.get_object("title")
        self.image = self.builder.get_object("image")
        self.adj = self.builder.get_object("adjustment")
        
        for f in self.target.features.values(): f.bind(
            gtk(lambda *args, f=f, **xargs: f==self._current_feature and self.on_value_change(*args,**xargs)))

    def set_value(self, value):
        self.scale.set_value(value)
        self.label.set_text(str(self._current_feature))
        
    @gtk
    def set_image(self, path):
        self.image.set_from_file(path)
        
    def on_change(self, event): self.on_widget_change()
    
    @property
    def visible(self): return self.window.get_visible()
    
    @gtk
    def show(self, f):
        self.on_value_change, self.on_widget_change = bind_widget_to_value(
            f.get, f.remote_set, self.scale.get_value,
            lambda value: f==self._current_feature and self.set_value(value))
        self.title.set_text(f.name)
        self.adj.set_lower(f.min)
        self.adj.set_upper(f.max)
        self._current_feature = f
        self.on_value_change()
        super().show()


class MenuMixin(TargetApp):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._header_items = {}
        self._footer_items = []
        self._menu = Gtk.Menu()

        # header features
        for f in self.target.features.values():
            try: item = self.add_feature(f, True)
            except TypeError: pass
            else: self._header_items[f] = item

        item_disconnected = Gtk.MenuItem("Connecting ...", sensitive=False)
        self._footer_items.append(item_disconnected)
        self.target.bind(on_connect = gtk(item_disconnected.hide))
        self.target.bind(on_disconnected = gtk(item_disconnected.show))

        item_more = Gtk.MenuItem("All Settings", no_show_all=True)
        self.target.bind(on_connect = gtk(item_more.show))
        self.target.bind(on_disconnected = gtk(item_more.hide))
        submenu = Gtk.Menu()
        categories = {cat: {"menu":Gtk.Menu(), "item":Gtk.MenuItem(cat, no_show_all=True)}
            for cat in self.target.feature_categories}
        for d in categories.values():
            submenu.append(d["item"])
            d["item"].set_submenu(d["menu"])
            self.target.bind(on_disconnected=gtk(lambda i=d["item"]: i.hide()))
        for key, f in self.target.features.items():
            d = categories[f.category]
            try: d["menu"].append(self.add_feature(f, False))
            except TypeError: pass
            else: f.bind(on_set = gtk(lambda i=d["item"]: i.show()))
        self.target.preload_features[-10].update(self.target.features)
        item_more.set_submenu(submenu)
        self._footer_items.append(item_more)

        self._footer_items.append(Gtk.SeparatorMenuItem())

        item_poweron = Gtk.CheckMenuItem("Auto power on")
        item_poweron.set_active(config["power_control"]["auto_power_on"])
        item_poweron.connect("toggled", lambda *args:
            [config["power_control"].__setitem__("auto_power_on",item_poweron.get_active()), config.save()])
        self.item_poweron = item_poweron
        self._footer_items.append(item_poweron)

        item_poweroff = Gtk.CheckMenuItem("Auto power off")
        item_poweroff.set_active(config["power_control"]["auto_power_off"])
        item_poweroff.connect("toggled", lambda *args:
            [config["power_control"].__setitem__("auto_power_off",item_poweroff.get_active()), config.save()])
        self.item_poweroff = item_poweroff
        self._footer_items.append(item_poweroff)

        self._footer_items.append(Gtk.SeparatorMenuItem())

        item_settings = Gtk.MenuItem('Program Settings')
        item_settings.connect('activate', lambda *args: self.settings.show())
        self._footer_items.append(item_settings)

        item_about = Gtk.MenuItem('About %s'%NAME)
        item_about.connect('activate', lambda *args: self.build_about_dialog())
        self._footer_items.append(item_about)

        item_quit = Gtk.MenuItem('Quit')
        item_quit.connect('activate', lambda *args: self.app_manager.main_quit())
        self._footer_items.append(item_quit)

        for e in self._footer_items+list(self._header_items.values()): e.show_all()

    def on_menu_settings_change(self, features):
        self.target.preload_features[2].clear()
        for f in features: self.target.preload_features[2].add(f.id)
        self._refill_menu(features)

    @gtk
    def _refill_menu(self, header_features):
        for child in self._menu.get_children(): self._menu.remove(child)
        for f in header_features:
            if item := self._header_items.get(f, None): self._menu.append(item)
        for item in self._footer_items: self._menu.append(item)

    def add_feature(self, f, compact=True):
        """ compact: If true, SelectFeatures show the value in the label.
        and BoolFeatures are Checkboxes without submenus. """
        if isinstance(f, features.BoolFeature): item = self._add_bool_feature(f, compact)
        elif isinstance(f, features.NumericFeature): item = self._add_numeric_feature(f, compact)
        elif isinstance(f, features.SelectFeature): item = self._add_select_feature(f, compact)
        else: raise TypeError(f"Unsupported feature type for {f.id}: {f.type}")
        item.set_no_show_all(True)
        f.bind(on_set = gtk(item.show))
        f.bind(on_unset = gtk(item.hide))
        return item

    def _add_bool_feature(self, f, compact):
        if not compact: return self._add_select_feature(f, compact)
        item = Gtk.CheckMenuItem(f.name)
        on_value_change, on_widget_change = bind_widget_to_value(
            f.get, f.remote_set, item.get_active, item.set_active)
        f.bind(gtk(on_value_change))
        item.connect("toggled", lambda event:on_widget_change())
        return item

    def _add_numeric_feature(self, f, compact):
        item = Gtk.MenuItem(f.name)
        def set(value): item.set_label(f"{f.name}   {f}")
        f.bind(gtk(set))
        item.connect("activate", lambda event:self.scale_popup.show(f))
        return item

    def _add_select_feature(self, f, compact):
        submenu = Gtk.Menu()
        item = Gtk.MenuItem(f.name, submenu=submenu)
        if compact: f.bind(gtk(item.set_label))
        f.bind(gtk(lambda value:self._refill_submenu(f, value, submenu, compact)))
        return item

    def _refill_submenu(self, f, value, submenu, compact):
        submenu.foreach(lambda child: child.destroy())
        if compact:
            submenu.append(Gtk.MenuItem(f.name, sensitive=False))
            submenu.append(Gtk.SeparatorMenuItem())
        if value not in f.options:
            submenu.append(Gtk.CheckMenuItem(value, sensitive=False, active=True, draw_as_radio=True))
        for o in f.options:
            active = value==o
            label = {True: "On", False: "Off"}.get(o, o)
            item = Gtk.CheckMenuItem(label, active=active, draw_as_radio=True)
            def on_activate(item, o=o, active=active):
                if item.get_active() != active:
                    item.set_active(active)
                    f.remote_set(o)
            item.connect("activate", on_activate)
            submenu.append(item)
        submenu.show_all()


class Icon(Bindable):
    """ Functions regarding loading images from src/share """
    
    def __init__(self, target):
        self.target = target
        self._icon_name = None
        self.target.bind(
            on_connect=self.update_icon,
            on_disconnected=self.set_icon,
            on_feature_change=self.on_feature_change)
        self.target.preload_features[10].update(self.relevant_features())

    def relevant_features(self): return config.tray_feature, config.muted, config.power

    def on_feature_change(self, f_id, value, *args): # bound to target
        if f_id in self.relevant_features(): self.update_icon()

    def update_icon(self):
        f = self.target.features.get(config.tray_feature)
        if (power := self.target.features.get(config.power)) and power.is_set() and power.get() == False:
            return self.set_icon("power")
        if (muted := self.target.features.get(config.muted)) and muted.is_set() and muted.get():
            return self.set_icon("audio-volume-muted")
        if f and f.is_set():
            f_val = f.get()
            if not (f.min <= f_val <= f.max):
                sys.stderr.write(
                    f"[{self.__class__.__name__}] WARNING: Value out of bounds: {f_val} for {f.id}.\n")
            if f_val <= f.min: return self.set_icon("audio-volume-muted")
            icons = ["audio-volume-low", "audio-volume-medium", "audio-volume-high"]
            icon_idx = math.ceil(min(1, (f_val-f.min)/(f.max-f.min))*len(icons))-1
            return self.set_icon(icons[icon_idx])
        self.set_icon("logo")

    def set_icon(self, name="disconnected"):
        if self._icon_name == name: return
        self._icon_name = name
        image_data = pkgutil.get_data(__name__, f"../share/icons/scalable/{name}.svg")
        with open(self._path, "wb") as fp: fp.write(image_data)
        self.on_change(self._path, name)

    def on_change(self, path, name): pass
    
    def __enter__(self):
        self._path = tempfile.mktemp()
        self.set_icon()
        return self

    def __exit__(self, *args):
        try: os.remove(self._path)
        except FileNotFoundError: pass


class Tray(MenuMixin, TargetApp):
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.settings = Settings(
            self.app_manager, self.target, on_menu_settings_change=self.on_menu_settings_change)
        self._app_indicator = AppIndicator3.Indicator.new(
            APP_NAME, APP_NAME, AppIndicator3.IndicatorCategory.HARDWARE)
        self.scale_popup = ScalePopup(self.target)
        self._app_indicator.connect("scroll-event", self.on_scroll)
        self._app_indicator.set_menu(self._menu)

    def on_scroll_up(self, steps): pass
    
    def on_scroll_down(self, steps): pass
    
    def build_about_dialog(self):
        ad = Gtk.AboutDialog()
        ad.set_program_name(APP_NAME)
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
    def show(self): self._app_indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    
    @gtk
    def hide(self): self._app_indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
    
    @gtk
    def set_icon(self, *args): self._app_indicator.set_icon_full(*args)

    def __exit__(self, *args, **xargs):
        super().__exit__(*args, **xargs)
        self.settings.hide()
        self.hide()


class TrayMixin(Tray):
    """ Tray Icon """

    def __init__(self, *args, **xargs):
        super().__init__(*args,**xargs)
        self.target.preload_features.update((config.tray_feature, config.muted))
        self.icon = Icon(self.target)
        self.icon.bind(on_change = self.on_icon_change)
        self.show()

    def __enter__(self):
        self.icon.__enter__()
        return super().__enter__()

    def __exit__(self, *args, **xargs):
        super().__exit__(*args, **xargs)
        self.icon.__exit__(*args, **xargs)

    def on_icon_change(self, path, name):
        self.scale_popup.set_image(path)
        self.set_icon(path, name)

    def _save_set_feature_to_relative_value(self, f_id, add):
        f = self.target.features.get(f_id)
        if not f or not f.is_set(): return
        try:
            value = f.get()+add
            snapped_value = min(max(f.min, value), f.max)
            f.remote_set(snapped_value)
        except ConnectionError: pass

    def on_scroll_up(self, steps):
        self._save_set_feature_to_relative_value(
            config.tray_feature, steps*Decimal(config["tray"]["scroll_delta"]))

    def on_scroll_down(self, steps):
        self._save_set_feature_to_relative_value(
            config.tray_feature, steps*-1*Decimal(config["tray"]["scroll_delta"]))


