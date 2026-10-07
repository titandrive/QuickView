"""Navigation over Dolphin's actual accessible item order and rectangles."""
def target_index(items, current_path, direction):
    index = next((i for i, item in enumerate(items) if item['path'] == current_path), None)
    if index is None or not items:
        return None
    delta = -1 if direction in ('left', 'up') else 1
    # Left/right follow displayed model order. A one-column list uses it for all keys.
    xs = {round(item['rect'][0], 1) for item in items if item.get('rect')}
    if direction in ('left', 'right') or len(xs) <= 1:
        target = index + delta
        return target if 0 <= target < len(items) else index
    here = items[index].get('rect')
    if not here:
        return index
    x, y, width, height = here
    candidates = []
    for i, item in enumerate(items):
        rect = item.get('rect')
        if not rect:
            continue
        dx, dy, dw, dh = rect
        if (dy - y) * delta > 2:
            candidates.append((abs(dy-y), abs((dx+dw/2)-(x+width/2)), i))
    if not candidates:
        return index
    nearest_row = min(c[0] for c in candidates)
    row = [c for c in candidates if abs(c[0] - nearest_row) <= 2]
    return min(row, key=lambda c: (c[1], c[2]))[2]
