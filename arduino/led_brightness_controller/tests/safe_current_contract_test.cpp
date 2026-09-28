#include <assert.h>

#include "../safe_current_contract.h"

namespace {

using fast_ofm_safe_current::PwmCurrentMap;
using fast_ofm_safe_current::invalidMap;

PwmCurrentMap map(uint8_t low_pwm, uint16_t low_current, uint8_t high_pwm,
                  uint16_t high_current, uint16_t artifact_version = 1) {
  const PwmCurrentMap result = {fast_ofm_safe_current::kCurrentMapSchemaVersion,
                                artifact_version,
                                fast_ofm_safe_current::kRequiredMapPointCount,
                                {low_pwm, low_current},
                                {high_pwm, high_current}};
  return result;
}

void test_safe_reset_is_zero_and_unarmed() {
  const fast_ofm_safe_current::RuntimeOutputs outputs =
      fast_ofm_safe_current::safeZeroOutputs();
  assert(!outputs.armed);
  assert(outputs.red_pwm == 0);
  assert(outputs.green_pwm == 0);
  assert(outputs.white_pwm == 0);
}

void test_v5_migration_discards_255_brightness_but_keeps_calibration_evidence() {
  fast_ofm_safe_current::LegacyV5Storage legacy = {
      fast_ofm_safe_current::kConfigMagic,
      fast_ofm_safe_current::kLegacyV5ConfigVersion,
      255,
      255,
      255,
      {11, 121, 101},
      {12, 122, 102},
      {13, 123, 103},
      0,
  };
  legacy.checksum = fast_ofm_safe_current::checksumLegacyV5(legacy);
  const fast_ofm_safe_current::CalibrationStorageV6 migrated =
      fast_ofm_safe_current::migrateV5ToV6(legacy);
  assert(fast_ofm_safe_current::isValidV6(migrated));
  assert(migrated.red_cal.min_pwm == 11);
  assert(migrated.green_cal.max_pwm == 122);
  assert(migrated.white_cal.threshold_ma_x100 == 103);
  assert(!fast_ofm_safe_current::isValidCurrentMap(migrated.red_map));
  assert(!fast_ofm_safe_current::isValidCurrentMap(migrated.green_map));
  assert(!fast_ofm_safe_current::isValidCurrentMap(migrated.white_map));
  const fast_ofm_safe_current::RuntimeOutputs outputs =
      fast_ofm_safe_current::safeZeroOutputs();
  assert(!outputs.armed && outputs.red_pwm == 0 && outputs.green_pwm == 0 &&
         outputs.white_pwm == 0);
}

void test_checksum_rejects_corruption() {
  fast_ofm_safe_current::CalibrationStorageV6 stored = fast_ofm_safe_current::defaults();
  assert(fast_ofm_safe_current::isValidV6(stored));
  stored.red_cal.max_pwm = 254;
  assert(!fast_ofm_safe_current::isValidV6(stored));
}

void test_get_and_getcal_queries_are_read_only() {
  const fast_ofm_safe_current::CalibrationStorageV6 stored =
      fast_ofm_safe_current::defaults();
  const uint8_t before = stored.checksum;
  (void)fast_ofm_safe_current::isValidV6(stored);  // GET validity/status query
  (void)fast_ofm_safe_current::isValidCurrentMap(stored.red_map);  // GETCAL query
  assert(stored.checksum == before);
}

void test_missing_or_invalid_maps_reject_arming() {
  const PwmCurrentMap valid = map(20, 5000, 140, 35000);
  assert(!fast_ofm_safe_current::canArmForTargets(
      invalidMap(), valid, valid, 10000, 10000, 30000));

  PwmCurrentMap wrong_schema = valid;
  wrong_schema.schema_version = 2;
  assert(!fast_ofm_safe_current::canArmForTargets(
      valid, wrong_schema, valid, 10000, 10000, 30000));

  PwmCurrentMap unreachable = valid;
  unreachable.high.current_ma_x100 = 29999;
  assert(!fast_ofm_safe_current::canArmForTargets(
      valid, valid, unreachable, 10000, 10000, 30000));
}

void test_target_current_is_not_raw_pwm() {
  const PwmCurrentMap red = map(20, 5000, 120, 15000);
  // 100.00 mA is the midpoint of this calibration artifact, so it maps to 70;
  // a current target is never interpreted as a raw PWM value.
  assert(fast_ofm_safe_current::pwmForTarget(red, 10000) == 70);
  assert(fast_ofm_safe_current::pwmForTarget(red, 20000) == 0);
}

void test_channel_maps_are_independent() {
  const PwmCurrentMap red = map(20, 5000, 120, 15000);
  const PwmCurrentMap green = map(40, 5000, 200, 15000);
  const PwmCurrentMap white = map(10, 10000, 250, 40000);
  assert(fast_ofm_safe_current::pwmForTarget(red, 10000) == 70);
  assert(fast_ofm_safe_current::pwmForTarget(green, 10000) == 120);
  assert(fast_ofm_safe_current::pwmForTarget(white, 30000) == 170);
  assert(fast_ofm_safe_current::canArmForTargets(
      red, green, white, 10000, 10000, 30000));
}

}  // namespace

int main() {
  test_safe_reset_is_zero_and_unarmed();
  test_v5_migration_discards_255_brightness_but_keeps_calibration_evidence();
  test_checksum_rejects_corruption();
  test_get_and_getcal_queries_are_read_only();
  test_missing_or_invalid_maps_reject_arming();
  test_target_current_is_not_raw_pwm();
  test_channel_maps_are_independent();
  return 0;
}
