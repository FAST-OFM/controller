# Logical IO Alias Registry

Status: software-only domain config. This package does not flash firmware,
bind pins, toggle GPIO, command motion, trigger cameras or drive LEDs.

The registry maps logical scanner names such as `camera_or_sync_trigger` and
`led_white` to reviewed board pin tokens. It is config-backed: callers provide
an already parsed YAML/JSON-like mapping to `load_io_alias_registry_from_mapping`.

The registry keeps three concerns separate:

- logical alias name, for planner and protocol metadata;
- physical pin token, including Klipper-style inversion such as `!PB3`;
- declared output state, where `active_value` and `inactive_value` may remain
  `unknown`.

Unknown electrical values must stay `unknown` until evidence is added to the
config. The loader does not infer active/inactive levels from pin names,
inversion or candidate status.

Aliases may be `candidate`, `active`, `superseded` or `rejected`. Candidate
entries are accepted as reviewed metadata but are not active outputs.
Superseded or rejected pins listed under `rejected_active_pins` cannot be used
by an active alias unless that alias carries an explicit
`active_alias_reviewed: true` re-review marker in config.
