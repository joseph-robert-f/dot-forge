# Third-party notices

## Starter source

Dot Forge starter source is licensed under GNU GPL version 3 or, at your option, any later version. The full GPLv3 text is in LICENSE. This repository is distributed without warranty; see that license.

## Pinned external Lane A builder

The adapter targets [headless-blender-character-builder](https://github.com/joseph-robert-f/headless-blender-character-builder), commit `f31eef7f87ec8573a106c2f6dbd6f76a49da94ae`, licensed GPL-3.0-or-later. `upstream.lock.json` records the selected files and expected hashes. The integration invokes separately obtained reviewed source; it does not bundle the upstream runtime. Preserve upstream attribution, license and corresponding-source obligations when redistributing that source or derived distributions. Consult the [pinned upstream notices](https://github.com/joseph-robert-f/headless-blender-character-builder/blob/f31eef7f87ec8573a106c2f6dbd6f76a49da94ae/THIRD_PARTY_NOTICES.md).

This pin is Lane A. It is not the experimental detailed-cat implementation and does not establish acceptance of that separate model.

## Python and build tooling

Runtime orchestration uses the Python standard library and declares no third-party pip runtime dependencies. Python itself has its own [license](https://docs.python.org/3/license.html). `setuptools` is build tooling, under the MIT license; the build-tool record is in `dependency-lock.json`. No Python interpreter or setuptools distribution is shipped here. The lock file is an inventory, not proof of a hermetically installed build environment.

## Blender and future adapters

Blender is an external application with its own [licensing terms](https://www.blender.org/about/license/). Runtime version and provenance records are in `runtime-lock.json`; no Blender binary, container image, font package or runtime archive is distributed. Observed executable hashes are not vendor-distribution verification.

FreeCAD and 3D Slicer integrations are deferred. Their names in the roadmap do not mean their binaries, source or dependencies are included or that their licenses have been cleared for future redistribution.

## Assets and output

See ASSET_LICENSE.md for original bundled examples. This notice does not license third-party designs, reference images, trademarks, imported files or user-provided inputs. Review the exact contents of any new distribution, including runtime and asset licenses, before publishing it.
