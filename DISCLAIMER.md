# Safety and use disclaimer

This repository controls motors and illumination hardware. It is a research
prototype and is not clinically validated, certified as a medical device or
approved for unattended operation.

Incorrect pins, voltage levels, current limits or travel bounds can damage the
controller, motors, LEDs, microscope or specimen. Verify the exact board,
wiring and safe electrical limits independently. Begin with outputs disabled,
use bounded movement, maintain a physical power-removal path and do not treat
software position as encoder-confirmed position.

The software is provided under the GNU General Public License version 3 in
`LICENSE`, without warranty.
