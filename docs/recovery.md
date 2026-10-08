# Recovery and bundles

Every generation begins in a new directory. Existing outputs are not silently overwritten. A run retains the request, resolved profile, a source snapshot, stage journal, editable BLEND, printing STL, previews, metrics, reports and logs. A failure should retain the available evidence.

The journal records completed stage hashes. `resume` checks the request and implementation identity and rejects changed completed artifacts. An incomplete generation is retried in a newly named sibling attempt; the failed attempt stays available. A completed generation can be revalidated and missing previews rendered. A completed run is verified rather than assumed good from its directory name.

Resume is not a universal migration tool. Preserve the exact runtime as well as source and requests; confirm the actual runtime before continuing on another machine. Source identity checks do not, by themselves, guarantee an identical external application. If settings, runtime, source or geometry change, start a fresh run instead of forcing reuse.

Finalization writes `manifest.json`, then a `COMPLETE` marker bound to its hash. Completion means the evidence set was finalized, not that the model is print-approved. A blocked validation report can still be retained as complete diagnostic evidence.

The bundle includes the finalized run inventory with file sizes and SHA-256 hashes. `verify-bundle` checks internal integrity, exact inventory and the exported STL's relationship to the validation report. Archive path, duplication and size checks precede bounded temporary materialization; embedded code is not executed. Manifests are unsigned: a consistently forged bundle is not authenticated by matching hashes.

Use a fresh output filename for bundling; do not place the bundle inside its own run directory. Verify after moving or downloading a bundle. Review contents for private information before uploading, and verify that the intended recipient can open the durable copy.

See command help for the exact `--run`, `--output` and bundle path options. Preserve the original attempt whenever repairing geometry; rerun generation, independent validation and preview stages on the repair.

Integrity verification independently reruns required geometry gates; it does not trust a recorded pass label. It checks exact artifact inventories and hashes, and rejects an inconsistent manifest, report or mesh. Hashes still do not authenticate the author or prove the design matches intent.
