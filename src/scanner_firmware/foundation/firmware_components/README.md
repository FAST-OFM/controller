# firmware_components

Shared software-only interfaces for isolated scanner firmware components.

These interfaces define boundaries between platform config, geometry math,
autofocus metrics, calibration estimators, frame/event matching, illumination
timing, coordinate fusion, predictive Z planning and future controller
adapters.
They do not import Klipper, open serial ports, toggle GPIO, drive LEDs, command
motors, trigger cameras or flash firmware.

Component implementations should accept explicit configuration values and
measured inputs. Do not hide scanner constants in component code.
