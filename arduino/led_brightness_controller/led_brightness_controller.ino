#include <EEPROM.h>
#include <avr/wdt.h>

#include "safe_current_contract.h"

namespace {

using fast_ofm_safe_current::CalibrationRange;
using fast_ofm_safe_current::CalibrationStorageV6;
using fast_ofm_safe_current::LegacyV5Storage;
using fast_ofm_safe_current::PwmCurrentMap;

const unsigned long kBaudRate = 115200;
const unsigned long kPwmFrequencyHz = 62500;
const uint16_t kAdcReferenceMv = 1100;
const uint8_t kSenseSamples = 16;
const uint16_t kAdcSaturationCount = 1000;

struct ChannelHardware {
  const char *name;
  uint8_t pwm_pin;
  uint8_t sense_pin;
  uint16_t sense_resistor_milliohm;
};

const ChannelHardware kChannels[] = {
    {"RED", 9, A0, 12000},
    {"GREEN", 10, A1, 12000},
    {"WHITE", 3, A2, 12000},
};
const uint8_t kChannelCount = sizeof(kChannels) / sizeof(kChannels[0]);

CalibrationStorageV6 config;
char lineBuffer[100];
uint8_t lineLength = 0;
bool lineOverflow = false;

char *nextToken(char **cursor);
CalibrationRange *channelCalibration(const char *channel);
PwmCurrentMap *channelMap(const char *channel);
const ChannelHardware *channelHardware(const char *channel);
void forceSafeZero();

void captureResetCause(void) __attribute__((naked, used, section(".init3")));
void captureResetCause(void) {
  MCUSR = 0;
  wdt_disable();
}

void refreshChecksum() {
  config.magic = fast_ofm_safe_current::kConfigMagic;
  config.version = fast_ofm_safe_current::kConfigVersion;
  config.checksum = fast_ofm_safe_current::checksumV6(config);
}

void writeConfigToEeprom(const CalibrationStorageV6 &candidate) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&candidate);
  for (size_t i = 0; i < sizeof(CalibrationStorageV6); ++i) {
    EEPROM.write(i, bytes[i]);
  }
}

void readBytes(void *destination, size_t size) {
  uint8_t *bytes = reinterpret_cast<uint8_t *>(destination);
  for (size_t i = 0; i < size; ++i) {
    bytes[i] = EEPROM.read(i);
  }
}

bool readV6FromEeprom(CalibrationStorageV6 *stored) {
  readBytes(stored, sizeof(*stored));
  return fast_ofm_safe_current::isValidV6(*stored);
}

bool readLegacyV5FromEeprom(LegacyV5Storage *stored) {
  readBytes(stored, sizeof(*stored));
  return fast_ofm_safe_current::isValidLegacyV5(*stored);
}

// There is intentionally no path from a saved config to a non-zero OCR value.
// A v5 image can carry calibration ranges forward, but its saved PWM commands
// (including 255/255/255) are discarded permanently during migration.
void loadCalibrationStorage(const __FlashStringHelper *loaded_message) {
  forceSafeZero();
  CalibrationStorageV6 stored;
  if (readV6FromEeprom(&stored)) {
    config = stored;
    Serial.println(loaded_message);
    return;
  }

  LegacyV5Storage legacy;
  if (readLegacyV5FromEeprom(&legacy)) {
    config = fast_ofm_safe_current::migrateV5ToV6(legacy);
    writeConfigToEeprom(config);
    Serial.println(F("OK MIGRATED_V5 SAFE_ZERO ARMED=0"));
    return;
  }

  config = fast_ofm_safe_current::defaults();
  Serial.println(F("OK DEFAULTS SAFE_ZERO ARMED=0"));
}

void saveCalibrationStorage() {
  refreshChecksum();
  writeConfigToEeprom(config);
  Serial.println(F("OK CAL SAVED SAFE_ZERO ARMED=0"));
}

void forceSafeZero() {
  OCR1A = 0;
  OCR1B = 0;
  OCR2B = 0;
}

void printConfig(const __FlashStringHelper *prefix) {
  // GET reports only actual output state.  It never exposes a stored command,
  // because commands are not persistent firmware calibration state.
  Serial.print(prefix);
  Serial.print(F(" RED_PWM=0 GREEN_PWM=0 WHITE_PWM=0 ARMED=0 PWM_HZ="));
  Serial.print(kPwmFrequencyHz);
  Serial.print(F(" CONFIG_VERSION="));
  Serial.println(fast_ofm_safe_current::kConfigVersion);
}

void printCalibrationRange(const __FlashStringHelper *name, const CalibrationRange &cal) {
  Serial.print(name);
  Serial.print(F("_MIN_PWM="));
  Serial.print(cal.min_pwm);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAX_PWM="));
  Serial.print(cal.max_pwm);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_THRESHOLD_MA_X100="));
  Serial.print(cal.threshold_ma_x100);
}

void printMap(const __FlashStringHelper *name, const PwmCurrentMap &map) {
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_VALID="));
  Serial.print(fast_ofm_safe_current::isValidCurrentMap(map) ? 1 : 0);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_SCHEMA="));
  Serial.print(map.schema_version);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_ARTIFACT_VERSION="));
  Serial.print(map.artifact_version);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_LOW_PWM="));
  Serial.print(map.low.pwm);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_LOW_MA_X100="));
  Serial.print(map.low.current_ma_x100);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_HIGH_PWM="));
  Serial.print(map.high.pwm);
  Serial.print(F(" "));
  Serial.print(name);
  Serial.print(F("_MAP_HIGH_MA_X100="));
  Serial.print(map.high.current_ma_x100);
}

void printCalibration(const __FlashStringHelper *prefix) {
  Serial.print(prefix);
  Serial.print(F(" "));
  printCalibrationRange(F("RED"), config.red_cal);
  printCalibrationRange(F(" GREEN"), config.green_cal);
  printCalibrationRange(F(" WHITE"), config.white_cal);
  printMap(F("RED"), config.red_map);
  printMap(F("GREEN"), config.green_map);
  printMap(F("WHITE"), config.white_map);
  Serial.println(F(" ARMED=0"));
}

void printPinLabel(uint8_t pin) {
  if (pin >= A0 && pin <= A5) {
    Serial.print(F("A"));
    Serial.print(pin - A0);
    return;
  }
  Serial.print(F("D"));
  Serial.print(pin);
}

void printHardwareSummary() {
  Serial.print(F("OK HARDWARE"));
  for (uint8_t i = 0; i < kChannelCount; ++i) {
    const ChannelHardware &hardware = kChannels[i];
    Serial.print(F(" "));
    Serial.print(hardware.name);
    Serial.print(F("_PWM="));
    printPinLabel(hardware.pwm_pin);
    Serial.print(F(" "));
    Serial.print(hardware.name);
    Serial.print(F("_SENSE="));
    printPinLabel(hardware.sense_pin);
    Serial.print(F(" "));
    Serial.print(hardware.name);
    Serial.print(F("_RSENSE_MOHM="));
    Serial.print(hardware.sense_resistor_milliohm);
  }
  Serial.print(F(" ADC_REF_MV="));
  Serial.print(kAdcReferenceMv);
  Serial.print(F(" PWM_HZ="));
  Serial.println(kPwmFrequencyHz);
}

uint16_t readAveragedAdc(uint8_t pin) {
  uint32_t total = 0;
  analogRead(pin);
  delayMicroseconds(100);
  for (uint8_t i = 0; i < kSenseSamples; ++i) {
    total += analogRead(pin);
  }
  return static_cast<uint16_t>((total + (kSenseSamples / 2)) / kSenseSamples);
}

uint16_t adcToMillivolts(uint16_t adc) {
  return static_cast<uint16_t>((static_cast<uint32_t>(adc) * kAdcReferenceMv + 511) / 1023);
}

uint16_t millivoltsToCentiamps(uint16_t millivolts, uint16_t sense_resistor_milliohm) {
  return static_cast<uint16_t>((static_cast<uint32_t>(millivolts) * 100000UL +
                                (sense_resistor_milliohm / 2)) /
                               sense_resistor_milliohm);
}

void printSenseChannel(const ChannelHardware &hardware) {
  const uint16_t adc = readAveragedAdc(hardware.sense_pin);
  const uint16_t millivolts = adcToMillivolts(adc);
  Serial.print(hardware.name);
  Serial.print(F("_ADC="));
  Serial.print(adc);
  Serial.print(F(" "));
  Serial.print(hardware.name);
  Serial.print(F("_MV="));
  Serial.print(millivolts);
  Serial.print(F(" "));
  Serial.print(hardware.name);
  Serial.print(F("_MA_X100="));
  Serial.print(millivoltsToCentiamps(millivolts, hardware.sense_resistor_milliohm));
}

void handleSense(char *cursor) {
  char *channel = nextToken(&cursor);
  if (channel == nullptr || strcmp(channel, "ALL") == 0) {
    Serial.print(F("OK SENSE "));
    for (uint8_t i = 0; i < kChannelCount; ++i) {
      if (i > 0) Serial.print(F(" "));
      printSenseChannel(kChannels[i]);
    }
    Serial.println();
    return;
  }
  const ChannelHardware *hardware = channelHardware(channel);
  if (hardware == nullptr) {
    Serial.println(F("ERR unknown channel"));
    return;
  }
  Serial.print(F("OK SENSE "));
  printSenseChannel(*hardware);
  Serial.println();
}

char *nextToken(char **cursor) { return strtok_r(*cursor, " \t", cursor); }

bool parseByte(const char *text, uint8_t *value) {
  if (text == nullptr || *text == '\0') return false;
  char *end = nullptr;
  const long parsed = strtol(text, &end, 10);
  if (*end != '\0' || parsed < 0 || parsed > 255) return false;
  *value = static_cast<uint8_t>(parsed);
  return true;
}

bool parseUInt16(const char *text, uint16_t *value) {
  if (text == nullptr || *text == '\0') return false;
  char *end = nullptr;
  const long parsed = strtol(text, &end, 10);
  if (*end != '\0' || parsed < 0 || parsed > 65535L) return false;
  *value = static_cast<uint16_t>(parsed);
  return true;
}

bool isSaveToken(const char *token) { return token != nullptr && strcmp(token, "SAVE") == 0; }

CalibrationRange *channelCalibration(const char *channel) {
  if (strcmp(channel, "RED") == 0) return &config.red_cal;
  if (strcmp(channel, "GREEN") == 0) return &config.green_cal;
  if (strcmp(channel, "WHITE") == 0) return &config.white_cal;
  return nullptr;
}

PwmCurrentMap *channelMap(const char *channel) {
  if (strcmp(channel, "RED") == 0) return &config.red_map;
  if (strcmp(channel, "GREEN") == 0) return &config.green_map;
  if (strcmp(channel, "WHITE") == 0) return &config.white_map;
  return nullptr;
}

const ChannelHardware *channelHardware(const char *channel) {
  for (uint8_t i = 0; i < kChannelCount; ++i) {
    if (strcmp(channel, kChannels[i].name) == 0) return &kChannels[i];
  }
  return nullptr;
}

void handleCal(char *cursor) {
  char *subcommand = nextToken(&cursor);
  if (subcommand == nullptr || strcmp(subcommand, "GET") == 0) {
    printCalibration(F("OK CAL"));
    return;
  }
  if (strcmp(subcommand, "SET") == 0) {
    char *channel = nextToken(&cursor);
    CalibrationRange *cal = channel == nullptr ? nullptr : channelCalibration(channel);
    uint8_t min_pwm = 0;
    uint8_t max_pwm = 0;
    if (cal == nullptr || !parseByte(nextToken(&cursor), &min_pwm) ||
        !parseByte(nextToken(&cursor), &max_pwm) || max_pwm <= min_pwm) {
      Serial.println(F("ERR CAL SET requires channel and min_pwm < max_pwm"));
      return;
    }
    uint16_t threshold = cal->threshold_ma_x100;
    char *token = nextToken(&cursor);
    if (token != nullptr && !isSaveToken(token) && !parseUInt16(token, &threshold)) {
      Serial.println(F("ERR CAL SET threshold must be 0-65535"));
      return;
    }
    char *save = isSaveToken(token) ? token : nextToken(&cursor);
    cal->min_pwm = min_pwm;
    cal->max_pwm = max_pwm;
    cal->threshold_ma_x100 = threshold;
    if (isSaveToken(save)) saveCalibrationStorage();
    else printCalibration(F("OK CAL SET"));
    return;
  }
  if (strcmp(subcommand, "MAP") == 0) {
    char *operation = nextToken(&cursor);
    if (operation != nullptr && strcmp(operation, "GET") == 0) {
      printCalibration(F("OK CAL MAP"));
      return;
    }
    if (operation == nullptr || strcmp(operation, "SET") != 0) {
      Serial.println(F("ERR CAL MAP requires GET or SET"));
      return;
    }
    char *channel = nextToken(&cursor);
    PwmCurrentMap *map = channel == nullptr ? nullptr : channelMap(channel);
    uint16_t artifact_version = 0;
    uint8_t low_pwm = 0;
    uint16_t low_current = 0;
    uint8_t high_pwm = 0;
    uint16_t high_current = 0;
    if (map == nullptr || !parseUInt16(nextToken(&cursor), &artifact_version) ||
        !parseByte(nextToken(&cursor), &low_pwm) || !parseUInt16(nextToken(&cursor), &low_current) ||
        !parseByte(nextToken(&cursor), &high_pwm) || !parseUInt16(nextToken(&cursor), &high_current)) {
      Serial.println(F("ERR CAL MAP SET requires channel version low_pwm low_ma high_pwm high_ma"));
      return;
    }
    PwmCurrentMap candidate = {fast_ofm_safe_current::kCurrentMapSchemaVersion,
                               artifact_version,
                               fast_ofm_safe_current::kRequiredMapPointCount,
                               {low_pwm, low_current},
                               {high_pwm, high_current}};
    if (!fast_ofm_safe_current::isValidCurrentMap(candidate)) {
      Serial.println(F("ERR CAL MAP invalid versioned PWM-to-current artifact"));
      return;
    }
    *map = candidate;
    if (isSaveToken(nextToken(&cursor))) saveCalibrationStorage();
    else printCalibration(F("OK CAL MAP SET"));
    return;
  }
  if (strcmp(subcommand, "RESET") == 0) {
    config = fast_ofm_safe_current::defaults();
    if (isSaveToken(nextToken(&cursor))) saveCalibrationStorage();
    else printCalibration(F("OK CAL RESET"));
    return;
  }
  if (strcmp(subcommand, "FIND") == 0) {
    Serial.println(F("ERR CAL FIND disabled: may not energize an unarmed channel"));
    return;
  }
  Serial.println(F("ERR unknown CAL command"));
}

void printHelp() {
  Serial.println(F("OK COMMANDS: PING HELP HARDWARE GET GETCAL SENSE CAL ZERO LOAD"));
  Serial.println(F("OK CAL: GET SET MAP GET|SET RESET; CAL FIND is disabled"));
  Serial.println(F("OK SAFE_CURRENT: SET SETC ARM ENABLE SAVE DEFAULTS are unavailable; ARMED=0"));
}

void handleCommand(char *line) {
  for (char *p = line; *p != '\0'; ++p) *p = toupper(*p);
  char *cursor = line;
  char *command = nextToken(&cursor);
  if (command == nullptr) return;
  if (strcmp(command, "PING") == 0) Serial.println(F("OK PONG SAFE_ZERO ARMED=0"));
  else if (strcmp(command, "HELP") == 0) printHelp();
  else if (strcmp(command, "HARDWARE") == 0) printHardwareSummary();
  else if (strcmp(command, "GET") == 0) printConfig(F("OK"));
  else if (strcmp(command, "GETCAL") == 0) printCalibration(F("OK CAL"));
  else if (strcmp(command, "SENSE") == 0) handleSense(cursor);
  else if (strcmp(command, "CAL") == 0) handleCal(cursor);
  else if (strcmp(command, "ZERO") == 0) {
    forceSafeZero();
    printConfig(F("OK ZERO"));
  } else if (strcmp(command, "LOAD") == 0) {
    loadCalibrationStorage(F("OK LOADED SAFE_ZERO ARMED=0"));
  } else if (strcmp(command, "SET") == 0 || strcmp(command, "SETC") == 0 ||
             strcmp(command, "ARM") == 0 || strcmp(command, "ENABLE") == 0 ||
             strcmp(command, "SAVE") == 0 || strcmp(command, "DEFAULTS") == 0) {
    forceSafeZero();
    Serial.println(F("ERR unarmed safe-current firmware: reviewed ARM/ENABLE path unavailable"));
  } else {
    Serial.println(F("ERR unknown command"));
  }
}

void processSerial() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      if (lineOverflow) {
        lineOverflow = false;
        lineLength = 0;
        Serial.println(F("ERR line too long"));
        return;
      }
      lineBuffer[lineLength] = '\0';
      handleCommand(lineBuffer);
      lineLength = 0;
      return;
    }
    if (lineOverflow) continue;
    if (lineLength < sizeof(lineBuffer) - 1) lineBuffer[lineLength++] = c;
    else {
      lineOverflow = true;
      lineLength = 0;
    }
  }
}

void setupHighFrequencyPwm() {
  for (uint8_t i = 0; i < kChannelCount; ++i) {
    pinMode(kChannels[i].pwm_pin, OUTPUT);
    digitalWrite(kChannels[i].pwm_pin, LOW);
  }
  forceSafeZero();
  TCCR1A = _BV(COM1A1) | _BV(COM1B1) | _BV(WGM10);
  TCCR1B = _BV(WGM12) | _BV(CS10);
  TCCR2A = _BV(COM2B1) | _BV(WGM21) | _BV(WGM20);
  TCCR2B = _BV(CS20);
  forceSafeZero();
}

}  // namespace

void setup() {
  setupHighFrequencyPwm();
  analogReference(INTERNAL);
  Serial.begin(kBaudRate);
  loadCalibrationStorage(F("OK LOADED SAFE_ZERO ARMED=0"));
}

void loop() { processSerial(); }
