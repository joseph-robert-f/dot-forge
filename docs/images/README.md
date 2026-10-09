# README example images

These three images are curated documentation assets. They show the original bundled examples, not user designs. This is a narrow documentation exception to the guidance that generated run output stays outside source history. Do not add model files, private requests, logs, or full run directories here.

Each PNG is an unchanged 512 × 512 oblique render of the exported STL. The images were inspected before selection. They are not photographs of physical prints and do not establish print suitability.

## Source and license

- Source commit: `880a91afc04efc153ba43ccd7863517ee14baa92`
- Generated on Linux with Blender 4.3.2. The stepped solid also used FreeCAD 1.0.0 / Open CASCADE 7.8.1.
- License: GPL-3.0-or-later, under [the original example asset terms](../../ASSET_LICENSE.md).
- Generation command: `python -m printkit doctor --json --all-smoke NEW_DIRECTORY`, from a reviewed checkout with `PYTHONPATH=src` and the required installed applications.
- Selection: `NEW_DIRECTORY/GENERATOR_ID/previews/oblique.png`. No geometry, image content, or aspect ratio was changed.

## Image identity

The hashes below match the original run manifests. They identify the committed image bytes; they do not replace the full model validation evidence.

### calibration-block.png

- Request: [examples/calibration-part/request.json](../../examples/calibration-part/request.json)
- SHA-256: `730f06ee1336f6498e2169b3e7eef825f9e8a6faf6bfb9ee4978c27c752c2fd7`

### geometric-mascot.png

- Request: [examples/geometric-mascot/request.json](../../examples/geometric-mascot/request.json)
- SHA-256: `8c92f40e8523dcc95e94b44dcccf29f4f2fd30e2b9c2b51908517a637589a59f`

### freecad-stepped-block.png

- Request: [examples/freecad-stepped-part/request.json](../../examples/freecad-stepped-part/request.json)
- SHA-256: `95bbb5bc2d2b380d19b2032c11d3fe25abc2bf20d15440f45343c6d743b94ecc`

