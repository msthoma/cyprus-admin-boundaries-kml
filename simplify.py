"""Douglas-Peucker line simplification, shared by split_kml.py and build_map.py."""

from __future__ import annotations

Point = tuple[float, float]


def simplify(*, points: list[Point], tolerance: float) -> list[Point]:
    """Drop every point closer than `tolerance` to the line between its kept neighbours.

    Iterative rather than recursive so a ring of several thousand points
    does not hit the recursion limit.
    """
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = points[first], points[last]
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        best_index, best_dist_sq = -1, tolerance * tolerance
        for i in range(first + 1, last):
            px, py = points[i]
            if length_sq == 0:
                dist_sq = (px - x1) ** 2 + (py - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
                dist_sq = (px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2
            if dist_sq > best_dist_sq:
                best_index, best_dist_sq = i, dist_sq
        if best_index >= 0:
            keep[best_index] = True
            stack.append((first, best_index))
            stack.append((best_index, last))
    return [p for p, k in zip(points, keep) if k]
