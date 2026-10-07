#!/usr/bin/python
"""Read-only Dolphin view snapshot. Run out of process using system GI/AT-SPI."""
import json
import os
import sys

_bridge_ready = False


def snapshot(path):
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, Gio, GLib
    global _bridge_ready
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

    def walk(node, active=False, depth=0):
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
            if role in ('frame', 'window', 'dialog'):
                active = active or node.get_state_set().contains(Atspi.StateType.ACTIVE)
            if role in ('list', 'table', 'tree', 'tree table'):
                if name != os.path.basename(folder):
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
                    item_path = os.path.join(folder, item_name)
                    if item_name not in filenames:
                        continue
                    component = child.get_component_iface()
                    rect = component.get_extents(Atspi.CoordType.SCREEN) if component else None
                    if not rect or rect.width <= 0 or rect.height <= 0:
                        raise RuntimeError('Dolphin did not expose every item rectangle')
                    items.append({'path': item_path,
                                  'rect': [rect.x, rect.y, rect.width, rect.height]})
                    if item_name == filename:
                        selected = child.get_state_set().contains(Atspi.StateType.SELECTED)
                if items and any(i['path'] == path for i in items):
                    if node.get_child_count() > 10000:
                        raise RuntimeError('View too large to snapshot safely')
                    candidates.append((int(selected)*4 + int(active)*2, items))
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
    if root:
        for i in range(root.get_child_count()):
            app = root.get_child_at_index(i)
            if app and 'dolphin' in (app.get_name() or '').lower():
                walk(app)
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
    return {'items': candidates[0][1]}

def serve():
    # Keep GI imports and the accessibility connection warm between previews.
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi
    Atspi.set_timeout(400, 400)
    for line in sys.stdin:
        token = None
        try:
            request = json.loads(line)
            token = request['token']
            import time
            started = time.monotonic()
            result = snapshot(os.path.abspath(request['path']))
            result['elapsed_ms'] = round((time.monotonic()-started)*1000)
        except Exception as e:
            result = {'error': str(e)}
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
