# Source provenance

This clean snapshot was assembled from private engineering repositories without
copying their Git history.

## Controller source

- Source: private engineering snapshot; old repository name intentionally omitted
- Frozen tag: `v0.1.2-prototype.1`
- Annotated tag object: `7daccec1bb2d9a87a8537c54588ef4692a3d78a3`
- Commit: `e99af08ab0978de217e7f2db34374d70dec85ef3`
- Tree: `8e414dba797e45ad2d78569c1f9ad42154294e94`

## Vendored scanner-core package

The release vendors the pure-Python `scanner_core` package and its tests to
remove a private SSH dependency:

- Source: private engineering snapshot; old repository name intentionally omitted
- Commit: `f7e6907e76a18ad18a0deb16ac1d42f039c068ca`
- Tree: `c6a6d69ff720540513a7c8c26b896809875ee4e1`
- Commit subject: `Split telemetry public types`

Only `src/scanner_core` and its tests/fixtures are included. Internal agent
instructions and engineering-process documents are excluded.

The controller test suite also vendors
`specifications/frame-event-schema.yaml` from the frozen architecture source:

- Source: private architecture snapshot; old repository name intentionally omitted
- Commit: `c2d8e9d35918a319dc8705feaea1b1ee5e3b5d5c`
- Tree: `41d5feee99d5be6558df4c61321753ef39bcdb1e`

## Klipper-derived material

Files under the documented Klipper patch/configuration areas are modifications
or integration material for [Klipper](https://www.klipper3d.org/), which is
licensed under GPL version 3. The original Klipper project is not affiliated
with or responsible for Fast OFM.

The exact GPL paths are declared in `REUSE.toml`. Independently authored
controller, protocol and scheduling modules outside those paths do not copy
Klipper source and use the repository's noncommercial Fast OFM license.
