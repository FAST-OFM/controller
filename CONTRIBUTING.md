# Contributing

Read `STATUS.md`, `UPSTREAM.md`, and
`arduino/led_brightness_controller/SAFE_CURRENT_CONTRACT.md` before changing
controller behaviour. Keep deployed MKS/Klipper and Arduino support separate
from experimental scanner-sync work. Experimental outputs must remain disabled
by default.

Every change must identify the affected Fast OFM feature ID, preserve upstream
GPL notices, include host-side tests, and document the exact build toolchain.
Do not upload firmware or energize motors/lights as part of an automated test.
Never commit real credentials, private addresses, or machine-specific secrets.

Contributions must preserve the file-level boundary in `REUSE.toml`. By
contributing original material, the contributor agrees to license it under the
license already assigned to that path and confirms that they have authority to
do so. Do not move GPL-derived material into a PolyForm or CC-licensed path.
