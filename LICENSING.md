# Controller licensing

This repository has a deliberate file-level license boundary. `REUSE.toml` is
the machine-readable authority and the complete texts are in `LICENSES/`.

## Original Fast OFM software

The following independently authored areas are licensed under
`PolyForm-Noncommercial-1.0.0`:

- `src/`;
- `tests/`;
- `arduino/`;
- `scripts/`;
- the Python package/build definition and CI workflows.

The license permits personal research and noncommercial use, modification and
redistribution. It does not grant commercial use. A commercial license must be
obtained separately in writing.

## Original documentation and data

Documentation, board profiles, specifications, examples, configuration,
evidence and project metadata not listed in another section are licensed under
`CC-BY-NC-SA-4.0`.

## Klipper-derived material

`docs/patches/` and `docs/live-mks/` contain Klipper-derived patches or source
and remain `GPL-3.0-only`. The GPL permits commercial use, and no
noncommercial restriction is added to those files.

The original Fast OFM adapters communicate with Klipper through documented
configuration, command and event boundaries; they do not copy Klipper source
and are licensed separately under PolyForm Noncommercial.

## Earlier copies

The immutable `v0.2.0-prototype.1` snapshot remains available to its recipients
under the license stated in that version. The mixed noncommercial/GPL boundary
applies from `v0.2.0-prototype.2` onward.
