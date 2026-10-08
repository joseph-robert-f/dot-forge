"""Exact vertex identity and combinatorial surface checks, without welding."""
from collections import defaultdict
from .intersections import cross, sub, normal, rational, dot


def inspect_topology(triangles, budget_check=lambda: None):
    edges, incident = defaultdict(list), defaultdict(list)
    duplicates, seen, degenerate = [], {}, []
    for i, t in enumerate(triangles):
        budget_check()
        key = tuple(sorted(t))
        if key in seen: duplicates.append([seen[key], i])
        seen[key] = i
        if normal(rational(t)) == (0, 0, 0): degenerate.append(i)
        for p in set(t): incident[p].append(i)
        for j in range(3):
            a, b = t[j], t[(j+1)%3]
            edges[tuple(sorted((a, b)))].append((i, a, b))
    boundary = [e for e, fs in edges.items() if len(fs) == 1]
    nonmanifold = [e for e, fs in edges.items() if len(fs) > 2]
    inconsistent = [e for e, fs in edges.items() if len(fs) == 2 and fs[0][1:] == fs[1][1:]]
    adjacency = [set() for _ in triangles]
    for fs in edges.values():
        budget_check()
        ids = {x[0] for x in fs}
        # Connectivity needs a star, never a quadratic clique on a bad edge.
        if ids:
            root = next(iter(ids))
            adjacency[root].update(ids-{root})
            for i in ids:
                if i != root: adjacency[i].add(root)
    unseen, components = set(range(len(triangles))), []
    while unseen:
        stack, component = [unseen.pop()], []
        while stack:
            budget_check()
            i = stack.pop(); component.append(i)
            new = adjacency[i] & unseen
            unseen.difference_update(new); stack.extend(new)
        components.append(component)
    bad_vertices = []
    for p, ids in incident.items():
        budget_check()
        # A closed manifold vertex has a single cyclic link, including multiplicity.
        link = defaultdict(list)
        for i in ids:
            budget_check()
            others = [v for v in triangles[i] if v != p]
            if len(others) != 2: continue
            a, b = others
            link[a].append(b); link[b].append(a)
        if not link or any(len(n) != 2 for n in link.values()):
            bad_vertices.append(p); continue
        remaining = set(link); stack = [remaining.pop()]
        while stack:
            new = set(link[stack.pop()]) & remaining
            remaining.difference_update(new); stack.extend(new)
        if remaining: bad_vertices.append(p)
    volumes, volume_signs, volume_underflow_exact = [], [], {}
    for ids in components:
        origin = rational([triangles[ids[0]][0]])[0]
        volume6 = 0
        for i in ids:
            budget_check()
            a, b, c = [sub(v, origin) for v in rational(triangles[i])]
            volume6 += dot(a, cross(b, c))
        exact_volume = volume6 / 6
        volume = float(exact_volume)
        volume_signs.append((exact_volume > 0) - (exact_volume < 0))
        if exact_volume and volume == 0.0:
            volume_underflow_exact[str(len(volumes))] = str(exact_volume)
        volumes.append(volume)
    budget_check()
    return dict(boundary_edges=boundary, nonmanifold_edges=nonmanifold,
                nonmanifold_vertices=bad_vertices, inconsistent_edges=inconsistent,
                degenerate_faces=degenerate, duplicate_faces=duplicates,
                components=components, signed_volumes_mm3=volumes,
                signed_volume_signs=volume_signs, volume_underflow_exact_mm3=volume_underflow_exact)
