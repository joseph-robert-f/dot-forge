# Developing a model family

The consumer path accepts reviewed generator IDs and bounded data. Creating a new generator is a source-code development task, not a reason to accept Python, shell fragments, URLs or arbitrary file imports in requests.

For a new family:

1. Describe its intended shape, units, required features, valid parameter ranges and limitations. Establish original or compatible asset rights.
2. Add a strict request contract and explicit geometry expectations. Do not assume bounding-box agreement establishes feature completeness.
3. Implement native creation, STL export, native reopen and previews. Keep the printing mesh identifiable and preserve editable source.
4. Add valid fixtures, extreme allowed parameter combinations and targeted negative cases. Test false acceptance and false rejection.
5. Run independent exported-mesh checks. Record unknown gates and compare all requested features visually.
6. Review execution risks and retain actual resource metrics. New code needs appropriate review and isolation before execution.
7. Update licensing, compatibility and acceptance evidence only after the relevant tests pass.

The current `solid-single-part` profile intentionally excludes assemblies and hollow/nested-shell designs. Do not relax the component gate to introduce those models without defining shell semantics, clearances and fixtures. Do not silently fill holes, smooth features or union parts to obtain a successful report.
