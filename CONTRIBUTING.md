# Contributing

Start with a small change against the current source revision. Explain the intended behavior, compatibility impact and evidence. Never include secrets, private requests, generated native models, render output or personal machine paths in a pull request.

Use Python 3.11+ and keep runtime orchestration standard-library only unless a dependency is explicitly reviewed, pinned and licensed. Run the repository's source checks and tests using the commands in docs/quickstart.md. Runtime-dependent checks must say which exact Blender profile was used. A skipped or unavailable test is not a pass.

New generators need a bounded parameter contract, original or properly licensed assets, deterministic fixtures, dimension/component expectations, negative cases and visual review. Do not add arbitrary code execution to the request format. See docs/model-development.md.

Changes to validators require both rejection tests and valid counterexamples to guard against false positives. Preserve raw findings and unknown states. Do not lower a threshold or silently repair geometry merely to turn a failing fixture green.

Document limitations and update docs/acceptance.md with evidence before widening release claims. Lane A requires the pinned source and exact runtime; a different native example does not complete that migration.

Contributions must be original or supplied with compatible rights and attribution. Submitted source follows the repository's GPL-3.0-or-later license. Do not add application binaries without a separate redistribution review. Public pushes, releases and model uploads are separate authorized actions, not side effects of local development.
