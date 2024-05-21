import sys
from gi.repository import Gtk, GObject
from threading import Thread
from ...core.transmission.discovery import discover_targets, get_name
from ...core.config import config as main_config
from ... import Target
from ..common import gtk, config


class UriSettingMode:
    RADIO_NAME = ""

    def __init__(self, target_setup):
        self.target_setup = target_setup
        self.radio = self.target_setup.builder.get_object(self.RADIO_NAME)

    def is_active(self): return self.radio.get_active()
    def get_uri(self): raise NotImplementedError()
    def set_uri(self, uri, active_mode): raise NotImplementedError()
    def __str__(self): return self.RADIO_NAME
    def __eq__(self, o): return str(o) == str(self)


class DeviceListMode(UriSettingMode):
    RADIO_NAME = "devices_view_radiobutton"

    def get_uri(self):
        l, it = self.target_setup.devices_view.get_selection().get_selected()
        if it:
            name, target = l.get_value(it, 0)
            return target.uri
        else: sys.stderr.write("No item selected.\n")

    def set_uri(self, uri, active_mode):
        if active_mode == self:
            self.target_setup._add_target_to_list(Target(uri))
        elif active_mode: return # active_mode is set and not self
        self.radio.set_active(True)


class TextEditMode(UriSettingMode):
    RADIO_NAME = "uri_edit_radiobutton"

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.uri_edit = self.target_setup.builder.get_object("uri_edit")

    def get_uri(self):
        return self.uri_edit.get_text()

    def set_uri(self, uri, active_mode):
        self.uri_edit.set_text(uri)
        if active_mode == self:
            self.radio.set_active(True)


class DemoMode(UriSettingMode):
    RADIO_NAME = "demo_radiobutton"
    URI = "emulate:denon"

    def get_uri(self): return self.URI

    def set_uri(self, uri, active_mode):
        if active_mode == self:
            self.radio.set_active(True)


class DeviceListMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.devices_view = self.builder.get_object("devices_view")
        column = self.builder.get_object("devices_column")
        self.devices_list = Gtk.ListStore(GObject.TYPE_PYOBJECT)
        self.devices_view.set_model(self.devices_list)
        cell = Gtk.CellRendererText()
        column.set_cell_data_func(cell, self._set_devices_cell_text)
        column.pack_start(cell, True)

    def on_target_search_click(self, *args, **xargs):
        self.search_and_add_targets()

    def _show(self):
        super()._show()
        self.search_and_add_targets()

    @gtk
    def search_and_add_targets(self):
        Thread(target=self._search_and_add_targets, daemon=True, name="search_and_add_targets()").start()

    def _search_and_add_targets(self):
        gtk(lambda:self.builder.get_object("device_search_button").set_sensitive(False))()
        print("Starting search")
        try:
            discovered = [target for x in self.devices_list for name, target in x]
            try: new_targets = discover_targets()
            except OSError as e: print(f"[{self.__class__.__name__}] {repr(e)}")
            else:
                for target in new_targets:
                    if target in discovered: continue
                    self._add_target_to_list(target)
        finally:
            print("Finished search")
            gtk(lambda:self.builder.get_object("device_search_button").set_sensitive(True))()

    @gtk
    def _add_target_to_list(self, target):
        def set_name(target=target, i=len(self.devices_list)):
            if name := get_name(target):
                self.devices_list[i] = [(name, target)]
        treeiter = self.devices_list.append([(target.uri, target)])
        Thread(target=set_name, daemon=True, name="get_target_name").start()
        if not self.devices_view.get_cursor().path:
            path = self.devices_list.get_path(treeiter)
            self.devices_view.set_cursor(path)
            self.on_target_setup_changed()

    def _set_devices_cell_text(self, column, cell, model, it, data):
        name, target = model.get_value(it, 0)
        cell.set_property('text', name)

    @gtk
    def on_devices_view_button_release_event(self, *args, **xargs):
        self.builder.get_object("devices_view_radiobutton").set_active(True)
        self.on_target_setup_changed()

    def reset_target_setup(self):
        self.devices_list.clear()
        super().reset_target_setup()


class TextEditMixin:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.uri_edit_radio = self.builder.get_object("uri_edit_radiobutton")

    def on_uri_edit_changed(self, *args, **xargs):
        self.uri_edit_radio.set_active(True)
        self.on_target_setup_changed()


class Base:
    target = None
    uri = None

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._modes = {C:C(self) for C in (TextEditMode, DemoMode, DeviceListMode)}
        self._device_settings = self.builder.get_object("device_settings")

    @gtk
    def show(self): self._show()

    def _show(self):
        self.reset_target_setup()
        super().show()

    def reset_target_setup(self):
        uri = main_config["Target"]["uri"]
        target_setup_mode = config["target"]["setup_mode"]
        for m in self._modes.values():
            m.set_uri(uri, target_setup_mode)
        self.on_target_setup_changed()

    def on_device_settings_radiobutton_toggled(self, *args, **xargs):
        self.on_target_setup_changed()

    def on_target_setup_changed(self):
        for self.mode in self._modes.values():
            if self.mode.is_active(): break
        uri = self.mode.get_uri()
        if uri == self.uri: return
        self.uri = uri
        self.window.set_page_complete(self._device_settings, False)
        if uri is not None:
            Thread(target=self.set_new_target, name="set_new_target", daemon=True).start()

    def set_new_target(self):
        if self.target: self.target.stop()
        try: self.target = Target(self.uri, connect=False)
        except Exception as e:
            sys.stderr.write(f"Could not create target for URI '{self.uri}': {e}\n")
            self.target = None
        else:
            self.target.start()
            self.window.set_page_complete(self._device_settings, True)

    def on_window_close(self, *args):
        if self.target:
            self.target.stop()
            self.target = None
        super().on_window_close(*args)

    def on_window_apply(self, *args):
        super().on_window_apply(*args)
        main_config["Target"]["uri"] = self.uri
        config["target"]["setup_mode"] = str(self.mode)
        config.save()

    def show_error(self, text):
        diag = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR, 
            Gtk.ButtonsType.OK, text)
        diag.connect("response", lambda *_: diag.destroy())
        diag.run()


class TargetSetup(DeviceListMixin, TextEditMixin, Base): pass

