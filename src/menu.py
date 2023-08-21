import argparse, os, pkgutil, tempfile, sys, traceback
from decimal import Decimal
from .core.util.async_widget import bind_widget_to_value
from .core import shared_vars
from .core.config import config, DictConfig, CONFDIR
from . import Target, get_schemes, NAME, VERSION, AUTHOR, COPYRIGHT


TITLE = f"{NAME} Control Menu"
os.environ["KIVY_NO_ARGS"] = "1"
parser = argparse.ArgumentParser(description=TITLE)
parser.add_argument('-t', '--target', metavar="URI", type=str, default=None, help='Target URI')
parser.add_argument('--verbose', '-v', action='count', default=0, help='Verbose mode')
cmd_args = parser.parse_args()


from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.gridlayout import GridLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.slider import Slider
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.uix.dropdown import DropDown
from kivy.uix.screenmanager import ScreenManager, Screen


class TabPanel(ScrollView):
    config = DictConfig("menu.json")
    _filter = lambda *_: False

    def __init__(self, target):
        self.target = target
        super().__init__()
        self.shared_vars = {}
        pinned = {True:[], False:[]}
        for f in self.target.shared_vars.values(): pinned[var.id in self.config["pinned"]].append(var)
        self._vars_stack = [*pinned[True], *pinned[False]]
        self.addSharedVarsFromStack(chunksize=50, repeat=None)
        
    def addSharedVarsFromStack(self, *_, chunksize=1, repeat=.1):
        chunk, self._vars_stack = self._vars_stack[:chunksize], self._vars_stack[chunksize:]
        for var in chunk:
            print("adding %s"%var.name)
            Clock.schedule_once(lambda *_, var=var: self.addSharedVar(var), 0)
        if repeat and self._vars_stack: Clock.schedule_once(self.addSharedVarsFromStack, repeat)

    def addSharedVar(self, var):
        self.target.preload_shared_vars.add(var.id)
        if self.target.connected:
            try: var.async_poll()
            except ConnectionError: pass
        row = VarRow()
        row.ids.text.text = var.name
        row.ids.checkbox.active = var.id in self.config["pinned"]

        if var.type == bool: w = self.addBoolVar(var)
        elif var.type == str: w = self.addSelectVar(var)
        elif var.type == int: w = self.addIntVar(var)
        elif var.type == Decimal: w = self.addDecimalVar(var)
        else: return print("WARNING: Not implemented: Shared var type '%s'"%var.type, file=sys.stderr)
        if w: row.ids.content.add_widget(w)
        
        def on_checkbox(checkbox, active):
            if active: self.config["pinned"].append(f.id)
            else: self.config["pinned"].remove(f.id)
            self.config.save()
        row.ids.checkbox.bind(active=on_checkbox)

        self.shared_vars[var.id] = row
        hide_widget(row)
        var.bind(on_set=lambda: Clock.schedule_once(lambda *_: show_widget(row), 0))
        var.bind(on_unset=lambda: Clock.schedule_once(lambda *_: hide_widget(row), 0))
        self.add_filtered(var.id, row)
        
    def _addNumericVar(self, var, from_widget=lambda n:n, step=None):
        panel = NumericVar()
        if step: panel.ids.slider.step = step
        
        def get(inst, value): return from_widget(panel.ids.slider.value)
        def set(value):
            panel.ids.slider.range = (float(var.min), float(var.max))
            panel.ids.slider.value = float(value)
            panel.ids.label.text = str(float(value))

        on_change = self.bind_widget_to_shared_var(var,get,set)
        panel.ids.slider.bind(value=on_change)
        return panel
    
    def addIntVar(self, var):
        return self._addNumericVar(var, from_widget=lambda n:int(n), step=1)
        
    def addDecimalVar(self, var):
        return self._addNumericVar(var, step=.5)

    def addBoolVar(self, var):
        bf = BoolVar()
        
        def get(inst):
            return inst.value if inst.state == "down" else not inst.value
            
        def set(value):
            trans = {False: "normal", True: "down"}
            bf.ids.on.state = trans[value]
            bf.ids.off.state = trans[not value]

        on_change = self.bind_widget_to_shared_var(var,get,set)
        bf.ids.on.bind(on_press=on_change)
        bf.ids.off.bind(on_press=on_change)
        return bf

    def addSelectVar(self, var):
        dropdown = SelectVarOptions()
        button = SelectVar()
        button.bind(on_release=lambda i: dropdown.open(i))
        
        def get(inst, value): return value
        def set(value):
            button.text = value
            Clock.schedule_once(lambda *_:update_options(), 0)
        
        def update_options():
            dropdown.clear_widgets()
            for text in var.options:
                o = SelectVarOption()
                o.text = text
                #o.bind(on_release=lambda i: dropdown.select(i.text))
                o.bind(on_press=lambda i: on_change(o,i.text))
                dropdown.add_widget(o)
            

        on_change = self.bind_widget_to_shared_var(var,get,set)
        #dropdown.bind(on_select=on_change)

        return button

    def filter(self, func):
        self._filter = func
        self.ids.layout.clear_widgets()
        for key, w in self.shared_vars.items(): self.add_filtered(key, w)

    def add_filtered(self, key, w):
        if self._filter(self.target.shared_vars[key]): self.ids.layout.add_widget(w)

    def bind_widget_to_shared_var(self, var, widget_getter, widget_setter):
        """ @var SharedVar object """
        on_value_change, on_widget_change = bind_widget_to_value(
            var.get, var.remote_set, widget_getter, widget_setter)
        var.bind(on_value_change)
        return on_widget_change


class TabHeader(ToggleButton):
    """ a tab header. shows self.panel when activated """

    def __init__(self, menu, *args, **xargs):
        super().__init__(*args, **xargs, group = "tab_header")
        self.content = menu.ids.menu_content
        self.bind(on_release = lambda *_: self.activate())

    def activate(self):
        self.state = "down"
        self.content.clear_widgets()
        self.content.add_widget(self.panel)


class CategoryTabHeader(TabHeader):

    def __init__(self, menu, *args, filter=None, **xargs):
        super().__init__(menu, *args, **xargs)
        self.panel = menu.panel
        if filter: self.filter = filter
        
    def activate(self):
        self.panel.filter(self.filter)
        super().activate()


class SettingsTabHeader(TabHeader):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.panel = SettingsTab()


class AboutTabHeader(TabHeader):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.panel = AboutTab()


class ConnectingTabHeader(TabHeader):
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.panel = ConnectingTab()
        hide_widget(self)


class ConnectingTab(Label): pass


class ScrollViewLayoutVertical(StackLayout):

    def __init__(self,*args,**xargs):
        super().__init__(*args,**xargs)
        self.bind(minimum_height=self.setter('height'))


class ScrollViewLayoutHorizontal(GridLayout):

    def __init__(self,*args,**xargs):
        super().__init__(*args,**xargs)
        self.bind(minimum_width=self.setter('width'))


class MyGrid(GridLayout): pass

class VarRow(MyGrid): pass

class NumericVar(GridLayout): pass

class SettingsTab(StackLayout): pass

class BoolVar(GridLayout): pass

class SelectVar(Button): pass

class SelectVarOptions(DropDown): pass

class SelectVarOption(Button): pass

class PinnedTab(CategoryTabHeader):
    text = "Pinned"
    filter = lambda self,f: f.id in self.panel.config["pinned"]

class AllTab(CategoryTabHeader):
    text = "All"
    filter = lambda self,f: True

class AboutTab(StackLayout):
    
    def __init__(self):
        super().__init__()
        self.ids.text.text = f"{TITLE}\nVersion {VERSION}\n{COPYRIGHT}\n"


class SettingsTab(StackLayout):

    def __init__(self):
        super().__init__()
        scheme_names = {S.scheme_id: S.get_title() for S in get_schemes()}
        dropdown = SelectVarOptions()
        self.ids.scheme.bind(on_release=lambda i: dropdown.open(i))
        for scheme, title in scheme_names.items():
            o = SelectVarOption()
            o.text = title
            o.bind(on_release=lambda e,scheme=scheme: dropdown.select(scheme))
            dropdown.add_widget(o)
        
        def on_select(e,scheme):
            self.scheme = scheme
            self.ids.scheme.text = scheme_names.get(scheme, scheme)
        dropdown.bind(on_select=on_select)
        
        uri = config.get("Target", "uri").split(":", 2)
        try:
            on_select(None, uri[0])
            self.ids.host.text = uri[1]
            self.ids.port.text = uri[2]
        except IndexError: pass

    def apply(self):
        parts = [self.scheme, self.ids.host.text.strip(), self.ids.port.text.strip()]
        config["Target"]["uri"] = ":".join(filter(lambda x:x, parts))
        App.get_running_app().load_screen()


class WelcomeScreen(Screen):

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        fd, icon_path = tempfile.mkstemp()
        with open(fd, "wb") as fp:
            fp.write(pkgutil.get_data(__name__,"share/icons/png/logo.png"))
        self.ids.image.source = icon_path
        os.remove(icon_path)


class _MenuScreen(Screen):

    def __init__(self, target=None, **kwargs):
        super().__init__()
        self.target = target
        #self.build()
        Clock.schedule_once(lambda *_:self.build(), .8) # TODO: instead do this on WelcomeScreen.on_enter. must be executed by Clock!

    def build(self):
        """ is being executed while showing Welcome screen """
        self.settings_tab = SettingsTabHeader(self)
        self.connecting_tab = ConnectingTabHeader(self)
        self.ids.headers.add_widget(self.settings_tab)
        self.ids.headers.add_widget(self.connecting_tab)
        self.ids.headers.add_widget(AboutTabHeader(self))
        App.get_running_app().manager.switch_to(self)
        

class ErrorScreen(_MenuScreen):

    def build(self):
        super().build()
        self.settings_tab.activate()
        

class MenuScreen(_MenuScreen):
    
    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self.target.shared_vars.name.bind(self.set_title)
        self.target.start()
    
    def set_title(self, name):
        App.get_running_app().title = "%s – %s"%(TITLE, name)
    
    def build(self):
        self.panel = TabPanel(self.target)
        self.pinned_tab = PinnedTab(self)
        self._visible_when_connected(self.pinned_tab)
        self.all_tab = AllTab(self)
        self._visible_when_connected(self.all_tab)
        categories = list(dict.fromkeys([var.category for var in self.target.shared_vars.values()]))
        tabs = {}
        for cat in categories:
            e = self._newTab(cat)
            tabs[cat] = e
            hide_widget(e)
            self.target.bind(on_disconnected = lambda e=e:Clock.schedule_once(lambda *_:hide_widget(e), 0))
        for key, var in self.target.shared_vars.items():
            var.bind(on_set = lambda cat=var.category: Clock.schedule_once(lambda *_:show_widget(tabs[cat]), 0))
        super().build()
        self.target.bind(on_connect=lambda:Clock.schedule_once(lambda *_:self.pinned_tab.activate(), 0))
        self.target.bind(on_disconnected=lambda:Clock.schedule_once(lambda *_:self.connecting_tab.activate(), 0))
        if self.target.connected: self.pinned_tab.activate()
        else: self.connecting_tab.activate()

    def _visible_when_connected(self, e):
        self.target.bind(on_connect = lambda:Clock.schedule_once(lambda *_: show_widget(e), 0))
        self.target.bind(on_disconnected = lambda:Clock.schedule_once(lambda *_: hide_widget(e), 0))
        if not self.target.connected: hide_widget(e)
        self.ids.headers.add_widget(e)

    def _newTab(self, category):
        def filter(f, category=category): return f.category == category
        header = CategoryTabHeader(self, text=category, filter=filter)
        self.ids.headers.add_widget(header)
        return header

    def on_enter(self): self.panel.addSharedVarsFromStack()
        
    def on_leave(self): self.target.stop()


def show_widget(w):
    old_attrs = widget_attrs.get(w)
    if old_attrs:
        w.height, w.size_hint_y, w.opacity, w.disabled, w.width, w.size_hint_x = old_attrs
        del widget_attrs[w]
    
def hide_widget(w):
    if w in widget_attrs: return #widget is already hidden
    widget_attrs[w] = w.height, w.size_hint_y, w.opacity, w.disabled, w.width, w.size_hint_x
    w.height = 0
    w.width = 0
    w.size_hint_x = None
    w.size_hint_y = None
    w.opacity = 0
    w.disabled = True

widget_attrs = {}


class App(App):

    def load_screen(self, *args, **xargs):
        self.title = TITLE
        self.manager.switch_to(WelcomeScreen())
        try: self.target = Target(*args, connect=False, verbose=cmd_args.verbose, **xargs)
        except Exception as e:
            print(traceback.format_exc())
            ErrorScreen()
        else: MenuScreen(self.target)

    def build(self):
        self.manager = ScreenManager()
        self.load_screen(cmd_args.target)
        return self.manager


kv = pkgutil.get_data(__name__,"share/menu.kv").decode()
Builder.load_string(kv)


def main():
    fd, icon_path = tempfile.mkstemp()
    try:
        with open(fd, "wb") as fp:
            fp.write(pkgutil.get_data(__name__,"share/icons/scalable/logo.svg"))
        app = App()
        app.icon = icon_path
        app.run()
    finally:
        try: app.target.stop()
        except: pass
        os.remove(icon_path)


if __name__ == "__main__": main()

