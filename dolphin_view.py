#!/usr/bin/python
"""Read-only Dolphin view snapshot. Run out of process using system GI/AT-SPI."""
import json
import os
import sys

_bridge_ready = False
_bound_view = None
_bound_items = {}


def search_item_path(child):
    """Resolve Dolphin's English accessibility Path field without guessing a folder."""
    name = child.get_name() or ''
    if not name or os.path.basename(name) != name:
        return None
    description = child.get_description() or ''
    if ', Path ' not in description:
        return None
    tail = description.split(', Path ', 1)[1]
    # Metadata follows the path. Check delimiter boundaries so commas in paths work.
    ends = [i for i in range(len(tail)) if tail.startswith(', ', i)] + [len(tail)]
    matches = set()
    for end in ends:
        parent = os.path.expanduser(tail[:end])
        if os.path.isabs(parent):
            candidate = os.path.join(parent, name)
            if os.path.exists(candidate):
                matches.add(candidate)
    return next(iter(matches)) if len(matches) == 1 else None


def snapshot(path, on_source_ready=None):
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, Gio, GLib
    global _bridge_ready, _bound_view, _bound_items
    _bound_view = None
    _bound_items = {}
    if not _bridge_ready:
        # One activation per helper lifetime, rather than a D-Bus write per preview.
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync('org.a11y.Bus', '/org/a11y/bus', 'org.freedesktop.DBus.Properties',
                      'Set', GLib.Variant('(ssv)', ('org.a11y.Status', 'IsEnabled',
                                                 GLib.Variant('b', True))),
                      None, Gio.DBusCallFlags.NONE, 1000, None)
        Atspi.set_timeout(400, 400)
        _bridge_ready = True
    folder = os.path.dirname(os.path.abspath(path))
    filename = os.path.basename(path)
    filenames = set(os.listdir(folder))
    candidates = []
    visited = 0

    def walk(node, active=False, depth=0, captured=False):
        nonlocal visited
        visited += 1
        if depth > 16 or visited > 4000:
            return
        try:
            role = node.get_role_name()
            if role in ('menu bar', 'menu item', 'popup menu', 'tool bar',
                        'button', 'combo box', 'text', 'entry', 'label',
                        'status bar', 'separator', 'scroll bar', 'slider'):
                return
            name = node.get_name() or '' if role in ('list', 'table', 'tree', 'tree table', 'panel') else ''
            if name == 'Places':
                return
            if not captured and role in ('frame', 'window', 'dialog'):
                active = active or node.get_state_set().contains(Atspi.StateType.ACTIVE)
            if role in ('list', 'table', 'tree', 'tree table'):
                search_view = not name
                if not search_view and name != os.path.basename(folder):
                    return  # Other folders and control lists cannot be this source view.
                items = []
                selected = False
                for i in range(min(node.get_child_count(), 10000)):
                    child = node.get_child_at_index(i)
                    if not child:
                        continue
                    if child.get_role_name() not in ('list item', 'table cell', 'tree item', 'icon'):
                        continue
                    item_name = child.get_name() or ''
                    # The accessible item name must be an exact filename in this folder.
                    if os.path.basename(item_name) != item_name:
                        continue
                    item_path = search_item_path(child) if search_view else os.path.join(folder, item_name)
                    if not item_path or (not search_view and item_name not in filenames):
                        continue
                    component = child.get_component_iface()
                    rect = component.get_extents(Atspi.CoordType.SCREEN) if component else None
                    if not rect or rect.width <= 0 or rect.height <= 0:
                        raise RuntimeError('Dolphin did not expose every item rectangle')
                    items.append({'path': item_path, 'source_index': i,
                                  'search_result': search_view,
                                  'rect': [rect.x, rect.y, rect.width, rect.height]})
                    if item_path == path:
                        selected = child.get_state_set().contains(Atspi.StateType.SELECTED)
                if items and any(i['path'] == path for i in items):
                    if node.get_child_count() > 10000:
                        raise RuntimeError('View too large to snapshot safely')
                    candidates.append((int(selected)*4 + int(active)*8, items, node))
                return
            for i in range(min(node.get_child_count(), 500)):
                child = node.get_child_at_index(i)
                if child:
                    walk(child, active, depth+1)
        except RuntimeError:
            raise
        except Exception:
            return

    root = Atspi.get_desktop(0)
    source_windows = []
    if root:
        for i in range(root.get_child_count()):
            app = root.get_child_at_index(i)
            if app and 'dolphin' in (app.get_name() or '').lower():
                for j in range(app.get_child_count()):
                    window = app.get_child_at_index(j)
                    if window:
                        is_active = window.get_state_set().contains(Atspi.StateType.ACTIVE)
                        source_windows.append((window, is_active))
    # Foreground state is now fixed; the preview may activate while we read the layout.
    if on_source_ready:
        on_source_ready()
    for window, is_active in source_windows:
        walk(window, active=is_active, captured=True)
    if not candidates:
        return {'error': 'No matching Dolphin view found; alphabetical navigation is disabled'}
    candidates.sort(key=lambda c: c[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        # Identical views are safe only if order AND layout agree.
        first = candidates[0][1]
        normalized = lambda items: [(i['path'], i['rect'][0]-items[0]['rect'][0],
                                     i['rect'][1]-items[0]['rect'][1]) for i in items]
        if any(normalized(c[1]) != normalized(first) for c in candidates if c[0] == candidates[0][0]):
            return {'error': 'Multiple Dolphin views match; select the file in the intended view'}
    # Identical layouts suffice for reading, but not for choosing which view to edit.
    if len(candidates) == 1 or candidates[0][0] > candidates[1][0]:
        _bound_view = candidates[0][2]
        _bound_items = {item['path']: item for item in candidates[0][1]}
    return {'items': candidates[0][1]}


def select_path(path):
    if _bound_view is None or path not in _bound_items:
        return {'error': 'Source Dolphin view is ambiguous or no longer bound'}
    index = _bound_items[path]['source_index']
    child = _bound_view.get_child_at_index(index)
    # Do not select a different file if Dolphin's model changed since the snapshot.
    if (child is None or child.get_name() != os.path.basename(path)
            or (_bound_items[path].get('search_result') and search_item_path(child) != path)):
        return {'error': 'Dolphin view changed; reopen the preview to refresh it'}
    selection = _bound_view.get_selection_iface()
    if selection is None:
        return {'error': 'Dolphin does not expose a selection interface'}
    count = selection.get_n_selected_children()
    if count > 1:
        return {'error': 'Preserving a multiple-file Dolphin selection'}
    old = [selection.get_selected_child(i).get_index_in_parent() for i in range(count)]
    if not selection.clear_selection():
        return {'error': 'Dolphin refused to clear the old selection'}
    try:
        if not selection.select_child(index) or not selection.is_child_selected(index):
            raise RuntimeError('Dolphin refused to select the previewed file')
    except Exception as e:
        selection.clear_selection()
        for previous in old:
            selection.select_child(previous)
        return {'error': str(e)}
    # Reveal off-screen selections without activating Dolphin or opening the file.
    try:
        from gi.repository import Atspi
        component = child.get_component_iface()
        if component:
            component.scroll_to(Atspi.ScrollType.ANYWHERE)
    except Exception:
        pass
    return {'selected': True}

def serve():
    # Keep GI imports and the accessibility connection warm between previews.
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi
    Atspi.set_timeout(400, 400)
    bound_token = None
    for line in sys.stdin:
        token = None
        try:
            request = json.loads(line)
            token = request['token']
            import time
            started = time.monotonic()
            if request.get('action') == 'select':
                result = select_path(os.path.abspath(request['path'])) if token == bound_token else {'error': 'Stale preview selection request'}
                result['selection_only'] = True
            else:
                result = snapshot(os.path.abspath(request['path']),
                                  lambda: print(json.dumps({'token': token, 'source_ready': True}), flush=True))
                bound_token = token if result.get('items') else None
            result['elapsed_ms'] = round((time.monotonic()-started)*1000)
        except Exception as e:
            result = {'error': str(e)}
        if 'request' in locals() and request.get('action') == 'select':
            result['selection_only'] = True
        result['token'] = token
        print(json.dumps(result), flush=True)

if __name__ == '__main__':
    if '--server' in sys.argv:
        serve()
    else:
        try:
            result = snapshot(os.path.abspath(sys.argv[1]))
        except Exception as e:
            result = {'error': str(e)}
        print(json.dumps(result))
