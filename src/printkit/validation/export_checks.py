"""Strict STL parser. Validates all bytes; ignores only binary attribute words."""
import math
import re
import struct

MAX_BYTES = 16 * 1024 * 1024
MAX_TRIANGLES = 10000
MAX_COORDINATE_MM = 1e9


class MeshError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def parse_stl(data, budget_check=lambda: None, max_bytes=None, max_triangles=None):
    # Defaults are read at call time, so the module budgets stay the single source.
    max_bytes = MAX_BYTES if max_bytes is None else max_bytes
    max_triangles = MAX_TRIANGLES if max_triangles is None else max_triangles
    budget_check()
    if len(data) > max_bytes: raise MeshError('export_budget', 'STL exceeds byte budget')
    triangles = []
    if len(data) >= 84 and len(data) == 84 + 50 * struct.unpack_from('<I', data, 80)[0]:
        count = struct.unpack_from('<I', data, 80)[0]
        if count > max_triangles: raise MeshError('triangle_budget', 'STL exceeds triangle budget')
        for i in range(count):
            budget_check()
            values = struct.unpack_from('<12fH', data, 84+50*i)
            if not all(math.isfinite(v) for v in values[:12]):
                raise MeshError('finite_coordinates', 'Nonfinite normal or coordinate')
            triangles.append(tuple(tuple(values[3+3*j:6+3*j]) for j in range(3)))
        encoding = 'binary'
    else:
        try: text = data.decode('ascii')
        except UnicodeDecodeError as exc: raise MeshError('export_parse', 'Invalid STL encoding or binary byte count') from exc
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2 or not re.fullmatch(r'solid(?:\s+.*)?', lines[0]) or not re.fullmatch(r'endsolid(?:\s+.*)?', lines[-1]):
            raise MeshError('export_parse', 'Invalid or truncated STL envelope')
        body = lines[1:-1]
        if len(body) % 7: raise MeshError('export_parse', 'Incomplete ASCII facet or trailing data')
        if len(body)//7 > max_triangles: raise MeshError('triangle_budget', 'STL exceeds triangle budget')
        for i in range(0, len(body), 7):
            budget_check()
            facet = body[i:i+7]
            if not facet[0].startswith('facet normal ') or facet[1] != 'outer loop' or facet[5:] != ['endloop', 'endfacet']:
                raise MeshError('export_parse', 'Invalid ASCII facet syntax')
            rows = [facet[0].split()[2:]]
            for line in facet[2:5]:
                fields = line.split()
                if not fields or fields[0] != 'vertex': raise MeshError('export_parse', 'Invalid vertex syntax')
                rows.append(fields[1:])
            try:
                values = [tuple(float(v) for v in row) for row in rows]
                if any(len(row) != 3 for row in values): raise ValueError('wrong vector size')
            except ValueError as exc: raise MeshError('export_parse', 'Invalid numeric vector') from exc
            if not all(math.isfinite(v) for row in values for v in row):
                raise MeshError('finite_coordinates', 'Nonfinite normal or coordinate')
            triangles.append(tuple(values[1:]))
        encoding = 'ascii'
    if not triangles: raise MeshError('nonempty_mesh', 'STL contains no triangles')
    if any(abs(v) > MAX_COORDINATE_MM for t in triangles for p in t for v in p):
        raise MeshError('coordinate_budget', 'Coordinate exceeds supported magnitude (1e9 mm)')
    budget_check()
    return triangles, encoding
