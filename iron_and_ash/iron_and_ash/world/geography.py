"""Geography helpers over the static map: neighbours, pathfinding, distance.

Pure functions over ``mapdata`` only - no dependency on mutable world state - so
the military sim and the map UI can both lean on it without import cycles.
"""
from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional

from . import mapdata


def neighbors(province_id: str) -> List[str]:
    return mapdata.ADJACENCY.get(province_id, [])


def bfs_path(start: str, goal: str) -> List[str]:
    """Shortest hop path from start to goal inclusive, or [] if unreachable."""
    if start == goal:
        return [start]
    if start not in mapdata.ADJACENCY or goal not in mapdata.ADJACENCY:
        return []
    prev: Dict[str, str] = {start: start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in mapdata.ADJACENCY[cur]:
            if nxt not in prev:
                prev[nxt] = cur
                if nxt == goal:
                    return _reconstruct(prev, start, goal)
                q.append(nxt)
    return []


def _reconstruct(prev: Dict[str, str], start: str, goal: str) -> List[str]:
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def distance(start: str, goal: str) -> int:
    """Number of hops between two provinces, or -1 if unreachable."""
    path = bfs_path(start, goal)
    return len(path) - 1 if path else -1


def step_toward(start: str, goal: str) -> Optional[str]:
    """The next province to move into when marching from start to goal."""
    path = bfs_path(start, goal)
    if len(path) >= 2:
        return path[1]
    return None


def travel_days(dest_province: str) -> int:
    """Base days to march/travel into a province, from its terrain."""
    prov = mapdata.PROVINCES.get(dest_province)
    if not prov:
        return 3
    return mapdata.TERRAIN[prov.terrain].move_days
