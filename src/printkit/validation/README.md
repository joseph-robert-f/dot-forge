# Independent STL validation reference profile

`validate_mesh(path, request)` reads the printing file once, hashes those exact
bytes, and inspects the parsed triangles independently of any backend. It uses
only the Python standard library and never modifies or repairs an export.

The initial `solid-single-part` profile requires one closed, consistently
outward-oriented manifold surface. `allowed_components` must be 1. Multiple
shells, even individually valid ones, are blocked. Cavities and assemblies need
a future profile with explicit shell semantics. A unitless STL is interpreted
in millimeters under the request contract. Dimension tolerance affects only the
axis-aligned size comparison, not vertex welding or intersection predicates.

Binary STL must have exactly its declared byte length. ASCII STL uses a strict
facet-per-lines grammar and permits a solid name. Both normal vectors and vertex
coordinates must be finite. Binary coordinates are IEEE float32 values; ASCII
numeric coordinates are parsed to Python binary64. Geometric predicates then
use exact rational representations of those parsed values. ASCII values finer
than binary64 resolution do not define a higher-precision modeling interface.
No approximate welding is performed. Cracks smaller than dimensional tolerance
still fail topology.

Topology uses exact vertex identity, edge incidence, cyclic connected vertex
links, orientation consistency, and exact signed tetrahedral volume sums for
each edge-connected component. Duplicate faces are recognized regardless of
winding. Geometric checking uses an inclusive AABB sweep and exact rational
triangle intersection predicates, including projected coplanar intersections.
Adjacent faces may intersect only on their shared topological edge or vertex.
Shared-vertex zero-thickness shell contacts fail the vertex-link gate. Other
contacts fail intersections. Nonintersecting closed-shell nesting is checked
with exact ray parity, retrying deterministic rays if they hit edges/vertices.
Unresolved degeneracy is unknown, never success.

Resource bounds: 16 MiB input, 10,000 triangles, coordinate magnitude at most
1e9 mm, 200,000 exact candidate-pair tests, 4,000,000 broad-phase candidates,
and a 30-second cooperative geometry deadline. These are reference-validator
limits, not claims about supported production model complexity. The deadline
is checked throughout parsing/topology loops, between and after predicate calls,
and before the final verdict; it is not an OS-enforced hard timeout.
Input/triangle limits additionally bound initial parsing/topology work.
Shared-edge face connectivity uses linear star adjacency, even for pathological
nonmanifold inputs. Exact per-shell volume signs are preserved separately from
floating-point display metrics; underflowed values include exact rational evidence. Pair/time exhaustion
is an unknown required intersection check and blocks the geometry state.
A caller should also enforce its own process deadline.

`geometry_validated` requires every required finding to pass. Exceptions are
reported as unknown validator errors, with remaining geometry gates unknown.
Feature size, wall thickness, clearances, build-envelope fit, orientation,
supports, visual completeness, slicer behavior and real printing are separate
unknown/manual checks. Their presence does not certify those properties.
`print_state` remains `needs_review`, including for a valid calibration cube.

The adversarial test suite includes binary/ASCII goldens; translated solids;
missing, duplicate, degenerate and reversed faces; reversed shells; edge and
vertex nonmanifoldness; closed self-intersection; coplanar overlap; touching,
nested, overlapping and unexpected disconnected shells; malformed/nonfinite
exports; wrong scale; and fail-closed budget, timeout and validator failures.
