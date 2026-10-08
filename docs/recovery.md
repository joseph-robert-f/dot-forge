# Recovery and bundles

Every generation begins in a new directory. Existing outputs are not silently overwritten. A run retains the request, resolved profile, a source snapshot, stage journal, editable BLEND or FCStd (plus STEP for FreeCAD), printing STL, previews, metrics, reports and logs. A failure should retain the available evidence.

The journal records completed stage hashes. `resume` checks the request and implementation identity and rejects changed completed artifacts. An incomplete generation is retried in a newly named sibling attempt; the failed attempt stays available. A completed generation can be revalidated and missing previews rendered. A completed run is verified rather than assumed good from its directory name.

Resume is not a universal migration tool. Preserve the exact runtime as well as source and requests; confirm the actual runtime before continuing on another machine. Source identity checks do not, by themselves, guarantee an identical external application. If settings, runtime, source or geometry change, start a fresh run instead of forcing reuse.

Finalization writes `manifest.json`, then a `COMPLETE` marker bound to its hash. Completion means the evidence set was finalized, not that the model is print-approved. A blocked validation report can still be retained as complete diagnostic evidence.

The bundle includes the finalized run inventory with file sizes and SHA-256 hashes. `verify-bundle` checks internal integrity, exact inventory and the exported STL's relationship to the validation report. Archive path, duplication and size checks precede bounded temporary materialization; embedded code is not executed. Manifests are unsigned: a consistently forged bundle is not authenticated by matching hashes.

Use a fresh output filename for bundling; do not place the bundle inside its own run directory. Verify after moving or downloading a bundle. Review contents for private information before uploading, and verify that the intended recipient can open the durable copy.

See command help for the exact `--run`, `--output` and bundle path options. Preserve the original attempt whenever repairing geometry; rerun generation, independent validation and preview stages on the repair.

For a recorded geometry-validated claim, integrity verification independently reruns required geometry gates; it does not trust a recorded pass label. It checks exact artifact inventories and hashes, and rejects an inconsistent manifest, report or mesh. Hashes still do not authenticate the author or prove the design matches intent.

## Deliverable selection

Bundles include only the documented model, source, preview, logs and report artifacts. Process-HOME caches and unrelated root files stay in the private run directory and are not read into or added to the ZIP. The manifest records this selection policy. Exact inventory and hash verification apply to selected deliverables; ZIPs containing extra non-deliverable members are rejected. Adding an unrecorded file inside an artifact directory still invalidates the manifest. Symlink artifacts are never followed. No runtime cache is deleted by bundling.

Blocked validation is preserved as diagnostic evidence. A finalized blocked run can be bundled and checked for transport integrity even when the validator is unavailable; verification explicitly returns `geometry_state: blocked` and never upgrades it. A recorded `geometry_validated` claim still requires fresh independent validation and matching required gates. Treat bundle integrity success separately from model approval.
