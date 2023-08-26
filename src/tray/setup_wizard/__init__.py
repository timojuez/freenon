import pkgutil
from gi.repository import Gtk, GObject, GdkPixbuf, Gio
from ... import Target
from ...core.util.autostart import Autostart
from ...core import shared_vars
from ..common import GladeGtk, gtk, config, id_to_string, APP_NAME, SharedVarSelectorCombobox, SharedVarValueCombobox, AbstractApp, autostart
from .target_setup import TargetSetup


class _Base(GladeGtk):
    GLADE = "../share/setup_wizard.glade"

    def __init__(self, first_run=False, *args, **xargs):
        super().__init__(*args, **xargs)
        self.applied = False
        self.first_run = first_run
        self.window = self.builder.get_object("window")
        self.window.set_title(APP_NAME)
        self._set_image()
        self.builder.get_object("intro_label").set_text(f"{APP_NAME} Setup")

    def _set_image(self):
        image_data = pkgutil.get_data(__name__, "../../share/icons/scalable/logo.svg")
        input_stream = Gio.MemoryInputStream.new_from_data(image_data, None)
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream(input_stream, None)
        self.builder.get_object("image").set_from_pixbuf(pixbuf)

    def show(self):
        super().show()

    def on_window_prepare(self, assistant, page): pass

    def on_window_apply(self, assistant):
        self.applied = True

    def on_window_close(self, assistant):
        Gtk.main_quit() if self.first_run and not self.applied else self.window.destroy()


class InputsMixin(TargetSetup):
    input_settings = [
        # v name,   type
        ("power",   shared_vars.BoolVar),
        ("muted",   shared_vars.BoolVar),
        ("idle",    shared_vars.BoolVar),
        ("source",  shared_vars.SelectVar),
        ("volume",  shared_vars.NumericVar)
    ]

    def show(self, *args, **xargs):
        self.input_selectors = None
        super().show(*args, **xargs)
        self._setup_input_selectors()
        for v, sel in self.input_selectors.items(): sel.set_active(config["target"]["shared_vars"][f"{v}_id"])

    def on_window_prepare(self, assistant, page):
        super().on_window_prepare(assistant, page)
        if page == self.builder.get_object("inputs"):
            gtk(self._setup_input_selectors)()

    def _setup_input_selectors(self):
        self.input_selectors = {
            v:SharedVarSelectorCombobox(self.target, self.builder.get_object(f"{v}_var"), allow_types=(t,),
                items=[("None", None)])
            for v, t in self.input_settings}

    def on_selector_changed(self, *args): pass

    def on_window_apply(self, *args):
        super().on_window_apply(*args)
        for v, sel in self.input_selectors.items():
            config["target"]["shared_vars"][f"{v}_id"] = sel.get_active()
        config.save()


class SourceMixin(InputsMixin):
    source_selector = None
    source_id = None

    def show(self, *args, **xargs):
        super().show(*args, **xargs)
        self._setup_source_selector()
        self.source_selector.set_active(config["target"]["source"])
        self._update_source_id()

    def on_window_prepare(self, assistant, page):
        super().on_window_prepare(assistant, page)
        if page == self.builder.get_object("input_source"):
            gtk(self._setup_source_selector)()

    def _setup_source_selector(self):
        self.source_selector = SharedVarValueCombobox(
            self.target, self.builder.get_object("source_value"), self.source_id, items=[("None", None)])

    def on_selector_changed(self, *args):
        super().on_selector_changed(*args)
        self._update_source_id()

    def _update_source_id(self):
        source_id = self.input_selectors["source"].get_active() if self.input_selectors else None
        if source_id == self.source_id: return
        self.source_id = source_id
        if self.target and self.source_id and self.source_selector:
            self.target.schedule(gtk(lambda var: self.source_selector.set_active(var.get())),
                requires=(self.source_id,))

    def set_new_target(self):
        super().set_new_target()
        if self.target:
            self.target.bind(on_shared_var_change = self.on_target_shared_var_change)
            self._update_source_id()

    @gtk
    def on_target_shared_var_change(self, var_id, value):
        if self.source_selector and var_id == self.source_id:
            self.source_selector.set_active(value)

    def on_window_apply(self, *args):
        super().on_window_apply(*args)
        config["target"]["source"] = self.source_selector.get_active()
        config.save()


class AutostartMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.builder.get_object("outro_label").set_text(f"You are going to find {APP_NAME} in "
            "your tray icon panel.")

    def on_window_apply(self, assistant):
        super().on_window_apply(assistant)
        if self.builder.get_object("autostart_checkbox").get_active():
            autostart.set_active(True)


class SetupWizard(AbstractApp, AutostartMixin, SourceMixin, InputsMixin, TargetSetup, _Base):

    def on_window_apply(self, *args):
        super().on_window_apply(*args)
        self.app_manager.run_app() # restart

