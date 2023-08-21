"""
Creates a treeview inside a Gtk widget for drag n drop selection of shared variables
"""

__all__ = ["SharedVarSelectorView"]


from random import randint
from gi.repository import Gtk, Gdk, GObject
from ...core import shared_vars
from ...core.util import Bindable
from ..common import config, resolve_shared_var_id, id_to_string, id_to_shared_var


class AvailTreeStore(Gtk.TreeStore):
    """ Forbid dragging category items """

    def __init__(self, view, *args, **xargs):
        super().__init__(*args, **xargs)
        self._view = view

    def do_row_draggable(self, path):
        #return path.get_depth() > 1
        obj = self._view.get_model().get_value(self._view.get_model().get_iter(path), 0)
        return isinstance(obj, shared_vars.SharedVar)


class _Base:

    def __init__(self, target, parent_widget, title="", *args, **xargs):
        super().__init__(*args, **xargs)
        self.dnd_from_menu_info = randint(0,1000) # drag n drop id
        self.dnd_from_avail = [('a', Gtk.TargetFlags.SAME_APP, self.dnd_from_menu_info+1)]
        self.dnd_from_menu = [('b', Gtk.TargetFlags.SAME_APP, self.dnd_from_menu_info)]
        self.target = target
        self.title = title
        self.popup_menu_settings = Gtk.Paned()
        self.popup_menu_settings.show_all()
        parent_widget.pack_start(self.popup_menu_settings, True, True, 0)

    def on_view_drag_data_get(self, treeview, context, selection, info, timestamp):
        treeselection = treeview.get_selection()
        model, iter = treeselection.get_selected()
        obj = model.get_value(iter, 0)
        b = getattr(obj, "id", obj).encode()
        selection.set(Gdk.TARGET_STRING, 8, b)


class AvailableVarsList:

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        sw = Gtk.ScrolledWindow()
        self.popup_menu_settings.pack1(sw, False, True)
        view = Gtk.TreeView()
        view.connect("drag-data-get", self.on_view_drag_data_get)
        view.connect("drag-data-received", self.on_avail_view_drag_data_received)
        column = Gtk.TreeViewColumn()
        column.set_title("Available Functions")
        view.append_column(column)
        sw.add(view)
        sw.show_all()
        if self.target:
            avail_list = AvailTreeStore(view, GObject.TYPE_PYOBJECT)
            category = {c:avail_list.append(None, [c]) for c in self.target.shared_var_categories}
            for f in self.target.shared_vars.values(): avail_list.append(category[f.category], [f])
            view.set_model(avail_list)
            cell = Gtk.CellRendererText()
            column.set_cell_data_func(cell, self._set_avail_cell_text)
            column.pack_start(cell, True)
            #column.add_attribute(cell, "text", 0)

        view.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK, self.dnd_from_avail, Gdk.DragAction.COPY)
        view.enable_model_drag_dest(self.dnd_from_menu, Gdk.DragAction.MOVE)

    def _set_avail_cell_text(self, column, cell, model, it, data):
        obj = model.get_value(it, 0)
        s = getattr(obj, "name", obj)
        cell.set_property('text', s)

    def on_avail_view_drag_data_received(self, treeview, context, x, y, selection, info, timestamp):
        context.finish(True, True, timestamp)
        self.on_selected_vars_change()


class SelectedVarsList(Bindable):
    _value = list

    def __init__(self, *args, **xargs):
        super().__init__(*args, **xargs)
        self._value = self._value()
        sw = Gtk.ScrolledWindow()
        self.popup_menu_settings.pack2(sw, False, True)
        view = Gtk.TreeView()
        view.connect("drag-data-get", self.on_view_drag_data_get)
        view.connect("drag-data-received", self.on_menu_view_drag_data_received)
        view.connect("drag-drop", self.on_menu_view_drag_drop)
        column = Gtk.TreeViewColumn()
        column.set_title(self.title)
        view.append_column(column)
        sw.add(view)
        sw.show_all()

        self.menu_list = Gtk.ListStore(GObject.TYPE_PYOBJECT)
        view.set_model(self.menu_list)
        cell = Gtk.CellRendererText()
        column.set_cell_data_func(cell, self._set_menu_cell_text)
        column.pack_start(cell, True)

        view.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK, self.dnd_from_menu, Gdk.DragAction.MOVE)
        view.enable_model_drag_dest(self.dnd_from_avail+self.dnd_from_menu, Gdk.DragAction.MOVE)

    def on_change(self, f_ids): pass

    def _update_listeners(self, f_ids):
        shared_vars = [f for f_id in f_ids for f in
            [id_to_shared_var(self.target, resolve_shared_var_id(f_id))] if f]
        self.on_change(shared_vars)

    def get_value(self): return self._value

    def set_value(self, f_ids):
        self._value = f_ids
        self.menu_list.clear()
        for f_id in f_ids: self.menu_list.append([f_id])
        self._update_listeners(f_ids)

    def add_item(self, f_id):
        self.set_value([*self.get_value(), f_id])

    def _set_menu_cell_text(self, column, cell, model, it, data):
        f_id = model.get_value(it, 0)
        s = id_to_string(self.target, f_id)
        cell.set_property('text', s)

    def on_menu_view_drag_data_received(self, treeview, context, x, y, selection, info, timestamp):
        f_id = selection.get_text()
        if f_id in self._value: return context.finish(False, False, timestamp) # reject
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if drop_info:
            path, pos = drop_info
            drop_before = pos in (Gtk.TreeViewDropPosition.BEFORE, Gtk.TreeViewDropPosition.INTO_OR_BEFORE)
            insert = (self.menu_list.insert_before if drop_before
                else self.menu_list.insert_after)
            insert(self.menu_list.get_iter(path), [f_id])
            #widget.stop_emission('drag_data_received')
        else:
            self.menu_list.append([f_id])
        context.finish(True, info == self.dnd_from_menu_info, timestamp)
        self.on_selected_vars_change()

    def on_selected_vars_change(self):
        f_ids = [row[0] for row in self.menu_list]
        self._value = f_ids
        self._update_listeners(f_ids)

    def on_menu_view_drag_drop(self, treeview, context, x, y, time):
        context.finish(True, False, time)


class SharedVarSelectorView(SelectedVarsList, AvailableVarsList, _Base): pass


