# Third-party notices

This distribution vendors the following runtime files so the IFC viewer works
offline. The OrbitControls import specifier points to the local Three.js module;
no functional upstream code was changed.

## web-ifc 0.0.78

- Project: <https://github.com/ThatOpen/engine_web-ifc>
- Files: `web/vendor/web-ifc/`
- Licence: Mozilla Public License 2.0

The upstream licence text is included alongside the vendored files.

## IfcOpenShell 0.8.5

- Project: <https://github.com/IfcOpenShell/IfcOpenShell>
- Distribution: installed Python dependency; not vendored in this archive
- Licence: GNU Lesser General Public License 3.0 or later

## Three.js 0.180.0

- Project: <https://github.com/mrdoob/three.js>
- Files: `web/vendor/three/`
- Licence: MIT

The upstream licence text is included alongside the vendored files.

## Manifold 3.5.1

- Project: <https://github.com/elalish/manifold>
- Distribution: installed `manifold3d` Python dependency; not vendored in this archive
- Licence: Apache License 2.0
- Use: solid-mesh intersection and volume; IFC parsing/tessellation remain IfcOpenShell responsibilities
