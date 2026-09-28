#ifndef FAST_OFM_SAFE_CURRENT_CONTRACT_H
#define FAST_OFM_SAFE_CURRENT_CONTRACT_H

#include <stdint.h>

// This header deliberately has no Arduino dependency so the exact safety
// decisions can be exercised by a deterministic host-side unit test.
namespace fast_ofm_safe_current {

const uint32_t kConfigMagic = 0x48534C44UL;  // "HSLD"
const uint8_t kLegacyV5ConfigVersion = 5;
const uint8_t kConfigVersion = 6;
const uint8_t kCurrentMapSchemaVersion = 1;
const uint8_t kRequiredMapPointCount = 2;

struct CalibrationRange {
  uint8_t min_pwm;
  uint8_t max_pwm;
  uint16_t threshold_ma_x100;
} __attribute__((packed));

struct PwmCurrentPoint {
  uint8_t pwm;
  uint16_t current_ma_x100;
} __attribute__((packed));

// A map is calibration evidence, not a command.  artifact_version is assigned
// by the reviewed host calibration workflow; schema_version identifies this
// serialized representation.
struct PwmCurrentMap {
  uint8_t schema_version;
  uint16_t artifact_version;
  uint8_t point_count;
  PwmCurrentPoint low;
  PwmCurrentPoint high;
} __attribute__((packed));

// Exact legacy layout retained only for checksum-validated v5 migration.
// legacy_* fields are intentionally never copied into v6 state.
struct LegacyV5Storage {
  uint32_t magic;
  uint8_t version;
  uint8_t legacy_red_pwm;
  uint8_t legacy_green_pwm;
  uint8_t legacy_white_pwm;
  CalibrationRange red_cal;
  CalibrationRange green_cal;
  CalibrationRange white_cal;
  uint8_t checksum;
} __attribute__((packed));

struct CalibrationStorageV6 {
  uint32_t magic;
  uint8_t version;
  CalibrationRange red_cal;
  CalibrationRange green_cal;
  CalibrationRange white_cal;
  PwmCurrentMap red_map;
  PwmCurrentMap green_map;
  PwmCurrentMap white_map;
  uint8_t checksum;
} __attribute__((packed));

inline uint8_t checksum(const uint8_t *bytes, uint16_t size_without_checksum) {
  uint8_t result = 0;
  for (uint16_t index = 0; index < size_without_checksum; ++index) {
    result ^= bytes[index];
  }
  return result;
}

inline uint8_t checksumLegacyV5(const LegacyV5Storage &storage) {
  return checksum(reinterpret_cast<const uint8_t *>(&storage), sizeof(storage) - 1);
}

inline uint8_t checksumV6(const CalibrationStorageV6 &storage) {
  return checksum(reinterpret_cast<const uint8_t *>(&storage), sizeof(storage) - 1);
}

inline bool isValidLegacyV5(const LegacyV5Storage &storage) {
  return storage.magic == kConfigMagic && storage.version == kLegacyV5ConfigVersion &&
         storage.checksum == checksumLegacyV5(storage);
}

inline bool isValidV6(const CalibrationStorageV6 &storage) {
  return storage.magic == kConfigMagic && storage.version == kConfigVersion &&
         storage.checksum == checksumV6(storage);
}

inline PwmCurrentMap invalidMap() {
  const PwmCurrentMap map = {0, 0, 0, {0, 0}, {0, 0}};
  return map;
}

inline CalibrationStorageV6 defaults() {
  CalibrationStorageV6 storage = {
      kConfigMagic,
      kConfigVersion,
      {1, 255, 100},
      {1, 255, 100},
      {1, 255, 100},
      invalidMap(),
      invalidMap(),
      invalidMap(),
      0,
  };
  storage.checksum = checksumV6(storage);
  return storage;
}

inline CalibrationStorageV6 migrateV5ToV6(const LegacyV5Storage &legacy) {
  CalibrationStorageV6 migrated = defaults();
  if (!isValidLegacyV5(legacy)) {
    return migrated;
  }
  migrated.red_cal = legacy.red_cal;
  migrated.green_cal = legacy.green_cal;
  migrated.white_cal = legacy.white_cal;
  // Intentionally do not migrate legacy PWM commands.  v5 min/max ranges are
  // evidence only and do not constitute a PWM-to-current map.
  migrated.checksum = checksumV6(migrated);
  return migrated;
}

inline bool isValidCurrentMap(const PwmCurrentMap &map) {
  return map.schema_version == kCurrentMapSchemaVersion &&
         map.artifact_version > 0 &&
         map.point_count == kRequiredMapPointCount &&
         map.low.pwm < map.high.pwm &&
         map.low.current_ma_x100 < map.high.current_ma_x100;
}

inline bool isTargetReachable(const PwmCurrentMap &map, uint16_t target_ma_x100) {
  return isValidCurrentMap(map) && target_ma_x100 >= map.low.current_ma_x100 &&
         target_ma_x100 <= map.high.current_ma_x100;
}

inline uint8_t pwmForTarget(const PwmCurrentMap &map, uint16_t target_ma_x100) {
  if (!isTargetReachable(map, target_ma_x100)) {
    return 0;
  }

  const uint32_t current_span = map.high.current_ma_x100 - map.low.current_ma_x100;
  const uint32_t pwm_span = map.high.pwm - map.low.pwm;
  const uint32_t offset = target_ma_x100 - map.low.current_ma_x100;
  return static_cast<uint8_t>(map.low.pwm + (offset * pwm_span + current_span / 2) /
                                             current_span);
}

struct RuntimeOutputs {
  bool armed;
  uint8_t red_pwm;
  uint8_t green_pwm;
  uint8_t white_pwm;
};

inline RuntimeOutputs safeZeroOutputs() {
  const RuntimeOutputs outputs = {false, 0, 0, 0};
  return outputs;
}

// A future reviewed ARM/ENABLE handler must first call this validator with
// host-provided target currents.  The current firmware never calls it to drive
// a physical output.
inline bool canArmForTargets(const PwmCurrentMap &red_map,
                             const PwmCurrentMap &green_map,
                             const PwmCurrentMap &white_map,
                             uint16_t red_target_ma_x100,
                             uint16_t green_target_ma_x100,
                             uint16_t white_target_ma_x100) {
  return isTargetReachable(red_map, red_target_ma_x100) &&
         isTargetReachable(green_map, green_target_ma_x100) &&
         isTargetReachable(white_map, white_target_ma_x100);
}

}  // namespace fast_ofm_safe_current

#endif  // FAST_OFM_SAFE_CURRENT_CONTRACT_H
