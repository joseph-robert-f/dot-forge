# Third-party notices

## Starter source

Dot Forge starter source is licensed under GNU GPL version 3 or, at your option, any later version. The full GPLv3 text is in LICENSE. This repository is distributed without warranty; see that license.

## Optional pinned external Lane A builder

The adapter targets [headless-blender-character-builder](https://github.com/joseph-robert-f/headless-blender-character-builder), commit `f31eef7f87ec8573a106c2f6dbd6f76a49da94ae`, licensed GPL-3.0-or-later. `upstream.lock.json` records the selected files and expected hashes. The integration invokes separately obtained reviewed source; it does not bundle the upstream runtime. Preserve upstream attribution, license and corresponding-source obligations when redistributing that source or derived distributions. Consult the [pinned upstream notices](https://github.com/joseph-robert-f/headless-blender-character-builder/blob/f31eef7f87ec8573a106c2f6dbd6f76a49da94ae/THIRD_PARTY_NOTICES.md).

This pin is optional Lane A, separate from the default installed-native profile. Its Blender 4.5.12 LTS contract remains unchanged and blocked; it is not needed for the three default bounded generators. It is not the experimental detailed-cat implementation and does not establish acceptance of that separate model.

## Python and build tooling

Runtime orchestration uses the Python standard library and declares no third-party pip runtime dependencies. Python itself has its own [license](https://docs.python.org/3/license.html). `setuptools` is build tooling, under the MIT license; the build-tool record is in `dependency-lock.json`. No Python interpreter or setuptools distribution is shipped here. The lock file is an inventory, not proof of a hermetically installed build environment.

## Installed-native runtimes and optional tools

Blender is an external application with its own [licensing terms](https://www.blender.org/about/license/). Runtime version and provenance records are in `runtime-lock.json`; no Blender binary, container image, font package or runtime archive is distributed. Observed executable hashes are not vendor-distribution verification.

The FreeCAD adapter invokes separately installed FreeCAD 1.0.0 / Open CASCADE 7.8.1 native modules through system Python. [FreeCAD describes its main source as LGPL version 2 or later](https://www.freecad.org/contributing.php), with individual files and dependencies having their own notices. [Open CASCADE uses LGPL 2.1 with its additional exception](https://github.com/Open-Cascade-SAS/OCCT/blob/master/README.md). Consult the exact installed distribution and upstream licensing notices before any binary redistribution. This repository contains only the original adapter and generator source, not those applications or libraries. Detected 3D Slicer files may be reported as optional observational inventory; integration remains experimental/deferred. No Slicer binary is distributed and discovery does not establish an accepted workflow.

## Assets and output

See ASSET_LICENSE.md for original bundled examples. This notice does not license third-party designs, reference images, trademarks, imported files or user-provided inputs. Review the exact contents of any new distribution, including runtime and asset licenses, before publishing it.
