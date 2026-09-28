# Platform Config

Software-only aggregate configuration contracts for scanner initialization.

## Firmware Config Split Guard

`config_split.check_firmware_config_split_files()` and the
`scanner-firmware-config-split --check-static` CLI provide the firmware-side
ownership check required by the repository governance docs. The checker accepts
firmware/controller config surfaces such as controller identity, motion,
scanner-sync protocol, firmware scheduler and motor-controller abstractions.
It rejects Pi-owned runtime config fields for camera modes, image processing,
acquisition, autofocus, tiling, scan recipes and calibration registries.
It also rejects placeholder values such as `TODO` on hardware-sensitive
pin, rail, GPIO and homing paths; unresolved hardware must stay explicit as
`unknown`.

The CLI emits deterministic JSON and exits non-zero when forbidden runtime
fields are present. It performs only static file parsing and mapping
inspection; it does not contact controllers, open cameras, toggle GPIO, drive
LEDs, command motion or flash firmware.

## Legacy Aggregate Value Objects

The platform config layer combines validated domain configuration:

- platform profile and controller identity
- motion configuration
- IO aliases and output arming policy
- scan recipe constraints

It does not parse files, open serial ports, configure Klipper, open cameras,
toggle GPIO, run motors, power LEDs or flash firmware. File parsing and live
adapters should produce these value objects, then pass their derived booleans
into preflight/readiness gates.

`loader.load_platform_config_from_mapping()` is the software-only boundary for
already-read YAML/JSON-like data. It accepts only a nested mapping with
`profile`, `motion`, `io` and `scan_recipe` sections, rejects unknown
or missing required fields, and constructs the validated domain objects. It
does not read files; filesystem ownership stays outside this package.

Camera mode details such as crop, binning, exposure and pixel format are owned
by the camera configuration domain. This package only carries firmware-owned
camera trigger readiness through `io.camera_trigger_config_valid`.

`motion.homing_enabled` is the configuration-level homing gate. The current
MKS/A4988 setup must keep it `false` because no limit switches are connected
and the A4988 path does not provide driver-assisted end-of-travel detection.
Dry-run flows may still run with hardware outputs disabled, but real scan or
motion/homing readiness must remain blocked until a reviewed homing method is
added.
