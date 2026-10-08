# Validation explained

## Read the two states separately

`geometry_state: geometry_validated` means the required checks passed for the named `solid-single-part` profile on the recorded STL bytes. `geometry_state: blocked` means at least one required check failed or was unknown. `print_state: needs_review` remains separate even when geometry passes.

An unknown result is not a pass. A timeout, exception, missing runtime or exhausted intersection budget must not produce a successful geometry claim. File existence, a good-looking preview and positive total volume are insufficient evidence.

## Implemented geometry scope

The independent standard-library STL validator checks complete parsing, finite coordinates, nonempty geometry, axis-aligned dimensions and explicit tolerance, boundary/nonmanifold edges, vertex links, degenerate/duplicate faces, orientation consistency, connected components and positive signed volume per shell. It checks triangle intersections using an AABB broad phase and exact rational predicates, with bounded work, and checks shell nesting for the initial solid profile.

Coordinates are interpreted in millimeters by the request contract because STL does not store units. Vertex identity is exact; dimension tolerance is not used to weld cracks or hide defects. This is a one-solid profile. Assemblies, intentional cavities and multiple shells require another reviewed profile.

The intersection algorithm has finite time and pair budgets. Its exact predicates describe arithmetic on the exported coordinate values, not a proof of every modeling intent or real-world manufacturing tolerance. Review test coverage and failures before extending the supported geometry families.

## Remaining gates

Wall thickness, small features, clearances, orientation/supports, visual completeness, slicer checks and physical printing remain unknown in this preview. With an explicit FDM printer profile, the orchestrator compares requested axis-aligned dimensions to the selected build envelope; exported dimensions are checked separately. This limited fit check does not analyze margin, rotation or supports. The independent mesh report still leaves its own build-envelope check unknown. Supplying minimum wall or clearance values does not implement those analyses.

Preview rendering uses the exported printing STL. Inspect front, side, back, top and oblique views against the request. A watertight object can still lack a requested ear, connector or hole. Human visual approval is not inferred from rendering successfully.

Slice the exact validated STL using the intended printer, material, orientation and profile. Inspect repaired geometry, missing thin features, empty layers, islands and supports. Then assess a real print when dimensions, fit or use require it. Neither step is performed by this starter release. Safety-critical, structural, medical, food-contact, electrical and child-safety uses require additional assessment.

Hashes bind a report to file bytes. An unsigned self-consistent manifest does not prove authenticity, authorship, design correctness or print safety.
