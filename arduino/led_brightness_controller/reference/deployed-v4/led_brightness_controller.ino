#include <EEPROM.h>

namespace {

const uint32_t kMagic = 0x48534C44UL;  // "HSLD"
const uint32_t kRuntimeMagic = 0x48534C52UL;  // "HSLR"
const uint8_t kConfigVersion = 4;
const unsigned long kBaudRate = 115200;
const unsigned long kPwmFrequencyHz = 62500;
const uint16_t kAdcReferenceMv = 1100;
const uint8_t kSenseSamples = 16;
const uint16_t kDefaultThresholdMaX100 = 100;  // 1.00 mA threshold.
const uint8_t kDefaultCalFindDelayMs = 20;
const uint8_t kDefaultCalFindMaxPwm = 64;
const uint16_t kAdcSaturationCount = 1000;

struct ChannelHardware {
  const char *name;
  uint8_t pwm_pin;
  uint8_t sense_pin;
  uint16_t sense_resistor_milliohm;
};

const ChannelHardware kChannels[] = {
    {"RED", 9, A0, 10000},      // Timer1 OC1A
    {"GREEN", 10, A1, 10000},   // Timer1 OC1B
    {"WHITE", 3, A2, 12000},    // Timer2 OC2B, lab white channel, 12 ohm sense
};
const uint8_t kChannelCount = sizeof(kChannels) / sizeof(kChannels[0]);

struct ChannelCalibration {
  uint8_t min_pwm;
  uint8_t max_pwm;
  uint16_t threshold_ma_x100;
};

struct LedConfig {
  uint32_t magic;
  uint8_t version;
  uint8_t red;
  uint8_t green;
  uint8_t white;
  ChannelCalibration red_cal;
  ChannelCalibration green_cal;
  ChannelCalibration white_cal;
  uint8_t checksum;
};

struct RuntimeState {
  uint32_t magic;
  uint8_t version;
  uint8_t red;
  uint8_t green;
  uint8_t white;
  uint8_t checksum;
};

LedConfig config;
RuntimeState retainedRuntime __attribute__((section(".noinit")));
uint8_t resetCause __attribute__((section(".noinit")));
char lineBuffer[80];
uint8_t lineLength = 0;

char *nextToken(char **cursor);
uint8_t *channelValue(const char *channel);
ChannelCalibration *channelCalibration(const char *channel);
const ChannelHardware *channelHardware(const char *channel);
const __FlashStringHelper *channelName(const char *channel);
void commitLiveOutputs();
void refreshChecksum();

void captureResetCause(void) __attribute__((naked, used, section(".init3")));
void captureResetCause(void) {
  resetCause = MCUSR;
  MCUSR = 0;
}

uint8_t calculateChecksum(const LedConfig &candidate) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&candidate);
  uint8_t checksum = 0;
  for (size_t i = 0; i < sizeof(LedConfig) - 1; ++i) {
    checksum ^= bytes[i];
  }
  return checksum;
}

uint8_t calculateRuntimeChecksum(const RuntimeState &candidate) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&candidate);
  uint8_t checksum = 0;
  for (size_t i = 0; i < sizeof(RuntimeState) - 1; ++i) {
    checksum ^= bytes[i];
  }
  return checksum;
}

bool isValidRuntimeState(const RuntimeState &candidate) {
  return candidate.magic == kRuntimeMagic &&
         candidate.version == kConfigVersion &&
         candidate.checksum == calculateRuntimeChecksum(candidate);
}

void rememberRuntimeValues() {
  retainedRuntime.magic = kRuntimeMagic;
  retainedRuntime.version = kConfigVersion;
  retainedRuntime.red = config.red;
  retainedRuntime.green = config.green;
  retainedRuntime.white = config.white;
  retainedRuntime.checksum = calculateRuntimeChecksum(retainedRuntime);
}

bool restoreRetainedRuntimeValues() {
  const uint8_t unsafe_reset_causes = _BV(PORF) | _BV(BORF) | _BV(WDRF);
  const bool external_reset_only =
      (resetCause & _BV(EXTRF)) != 0 && (resetCause & unsafe_reset_causes) == 0;
  if (!external_reset_only) {
    return false;
  }

  if (!isValidRuntimeState(retainedRuntime)) {
    return false;
  }

  config.red = retainedRuntime.red;
  config.green = retainedRuntime.green;
  config.white = retainedRuntime.white;
  refreshChecksum();
  return true;
}

void setDefaults() {
  config.magic = kMagic;
  config.version = kConfigVersion;
  config.red = 0;
  config.green = 0;
  config.white = 0;
  config.red_cal = {1, 255, kDefaultThresholdMaX100};
  config.green_cal = {1, 255, kDefaultThresholdMaX100};
  config.white_cal = {1, 255, kDefaultThresholdMaX100};
  config.checksum = calculateChecksum(config);
}

void refreshChecksum(LedConfig &candidate) {
  candidate.magic = kMagic;
  candidate.version = kConfigVersion;
  candidate.checksum = calculateChecksum(candidate);
}

void refreshChecksum() {
  refreshChecksum(config);
}

bool isValidConfig(const LedConfig &candidate) {
  return candidate.magic == kMagic &&
         candidate.version == kConfigVersion &&
         candidate.checksum == calculateChecksum(candidate);
}

void applyOutputs() {
  OCR1A = config.red;
  OCR1B = config.green;
  OCR2B = config.white;
}

void commitLiveOutputs() {
  refreshChecksum();
  applyOutputs();
  rememberRuntimeValues();
}

void printConfig(const __FlashStringHelper *prefix) {
  Serial.print(prefix);
  Serial.print(F(" RED="));
  Serial.print(config.red);
  Serial.print(F(" GREEN="));
  Serial.print(config.green);
  Serial.print(F(" WHITE="));
  Serial.print(config.white);
  Serial.print(F(" PWM_HZ="));
  Serial.print(kPwmFrequencyHz);
  Serial.print(F(" CONFIG_VERSION="));
  Serial.println(kConfigVersion);
}

void printCalibrationChannel(const __FlashStringHelper *name, const ChannelCalibration &cal) {
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

void printCalibration(const __FlashStringHelper *prefix) {
  Serial.print(prefix);
  Serial.print(F(" "));
  printCalibrationChannel(F("RED"), config.red_cal);
  Serial.print(F(" "));
  printCalibrationChannel(F("GREEN"), config.green_cal);
  Serial.print(F(" "));
  printCalibrationChannel(F("WHITE"), config.white_cal);
  Serial.println();
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
  return static_cast<uint16_t>(
      (static_cast<uint32_t>(millivolts) * 100000UL + (sense_resistor_milliohm / 2)) /
      sense_resistor_milliohm);
}

void printSenseChannel(const ChannelHardware &hardware) {
  const uint16_t adc = readAveragedAdc(hardware.sense_pin);
  const uint16_t millivolts = adcToMillivolts(adc);
  const uint16_t centiamps =
      millivoltsToCentiamps(millivolts, hardware.sense_resistor_milliohm);

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
  Serial.print(centiamps);
  Serial.print(F(" "));
  Serial.print(hardware.name);
  Serial.print(F("_RSENSE_MOHM="));
  Serial.print(hardware.sense_resistor_milliohm);
}

void printSenseAll() {
  Serial.print(F("OK SENSE "));
  for (uint8_t i = 0; i < kChannelCount; ++i) {
    if (i > 0) {
      Serial.print(F(" "));
    }
    printSenseChannel(kChannels[i]);
  }
  Serial.print(F(" ADC_REF_MV="));
  Serial.println(kAdcReferenceMv);
}

void handleSense(char *cursor) {
  char *channel = nextToken(&cursor);
  if (channel == nullptr || strcmp(channel, "ALL") == 0) {
    printSenseAll();
    return;
  }

  const ChannelHardware *hardware = channelHardware(channel);
  if (hardware == nullptr) {
    Serial.println(F("ERR unknown channel"));
    return;
  }

  Serial.print(F("OK SENSE "));
  printSenseChannel(*hardware);
  Serial.print(F(" ADC_REF_MV="));
  Serial.println(kAdcReferenceMv);
}

void writeConfigToEeprom(const LedConfig &candidate) {
  const uint8_t *bytes = reinterpret_cast<const uint8_t *>(&candidate);
  for (size_t i = 0; i < sizeof(LedConfig); ++i) {
    EEPROM.write(i, bytes[i]);
  }
}

bool readConfigFromEeprom(LedConfig *stored) {
  uint8_t *bytes = reinterpret_cast<uint8_t *>(stored);
  for (size_t i = 0; i < sizeof(LedConfig); ++i) {
    bytes[i] = EEPROM.read(i);
  }
  return isValidConfig(*stored);
}

void saveConfig() {
  refreshChecksum();
  writeConfigToEeprom(config);
  rememberRuntimeValues();
  printConfig(F("OK SAVED"));
}

void saveCalibrationConfig() {
  LedConfig stored;
  if (!readConfigFromEeprom(&stored)) {
    stored = config;
    stored.red = 0;
    stored.green = 0;
    stored.white = 0;
  }

  stored.red_cal = config.red_cal;
  stored.green_cal = config.green_cal;
  stored.white_cal = config.white_cal;
  refreshChecksum(stored);
  writeConfigToEeprom(stored);
  printCalibration(F("OK CAL SAVED"));
}

void loadConfig() {
  LedConfig stored;
  if (readConfigFromEeprom(&stored)) {
    config = stored;
    commitLiveOutputs();
    printConfig(F("OK LOADED"));
    return;
  }

  setDefaults();
  commitLiveOutputs();
  printConfig(F("OK DEFAULTS"));
}

void loadStartupConfig() {
  LedConfig stored;
  const bool loaded = readConfigFromEeprom(&stored);
  if (loaded) {
    config = stored;
  } else {
    setDefaults();
  }

  const bool restored_runtime = restoreRetainedRuntimeValues();
  applyOutputs();

  if (restored_runtime) {
    printConfig(F("OK RUNTIME"));
    return;
  }
  printConfig(loaded ? F("OK LOADED") : F("OK DEFAULTS"));
}

char *nextToken(char **cursor) {
  char *token = strtok_r(*cursor, " \t", cursor);
  return token;
}

bool parseByte(const char *text, uint8_t *value) {
  if (text == nullptr || *text == '\0') {
    return false;
  }

  char *end = nullptr;
  const long parsed = strtol(text, &end, 10);
  if (*end != '\0' || parsed < 0 || parsed > 255) {
    return false;
  }

  *value = static_cast<uint8_t>(parsed);
  return true;
}

bool parseUInt16(const char *text, uint16_t *value) {
  if (text == nullptr || *text == '\0') {
    return false;
  }

  char *end = nullptr;
  const long parsed = strtol(text, &end, 10);
  if (*end != '\0' || parsed < 0 || parsed > 65535L) {
    return false;
  }

  *value = static_cast<uint16_t>(parsed);
  return true;
}

bool isSaveToken(const char *token) {
  return token != nullptr && strcmp(token, "SAVE") == 0;
}

void printHelp() {
  Serial.println(F("OK COMMANDS: PING HELP HARDWARE GET GETCAL SENSE SET SETC CAL ZERO SAVE LOAD DEFAULTS"));
  Serial.println(F("OK SET: SET RED|GREEN|WHITE <0-255> [SAVE]"));
  Serial.println(F("OK SET ALL: SET ALL <red> <green> <white> [SAVE]"));
  Serial.println(F("OK SETC: SETC RED|GREEN|WHITE <0-255> [SAVE]"));
  Serial.println(F("OK SETC ALL: SETC ALL <red> <green> <white> [SAVE]"));
  Serial.println(F("OK CAL SET: CAL SET RED|GREEN|WHITE <min_pwm> <max_pwm> [threshold_ma_x100] [SAVE]"));
  Serial.println(F("OK CAL FIND: CAL FIND RED|GREEN|WHITE [threshold_ma_x100] [delay_ms] [max_pwm] [SAVE]"));
  printHardwareSummary();
}

uint8_t calibratedToPwm(const ChannelCalibration &cal, uint8_t brightness) {
  if (brightness == 0) {
    return 0;
  }
  if (cal.max_pwm <= cal.min_pwm) {
    return brightness;
  }

  const uint16_t span = static_cast<uint16_t>(cal.max_pwm - cal.min_pwm);
  const uint16_t scaled =
      static_cast<uint16_t>(cal.min_pwm) +
      ((static_cast<uint32_t>(brightness - 1) * span + 127) / 254);
  return static_cast<uint8_t>(scaled > 255 ? 255 : scaled);
}

uint8_t *channelValue(const char *channel) {
  if (strcmp(channel, "RED") == 0) {
    return &config.red;
  }
  if (strcmp(channel, "GREEN") == 0) {
    return &config.green;
  }
  if (strcmp(channel, "WHITE") == 0) {
    return &config.white;
  }
  return nullptr;
}

ChannelCalibration *channelCalibration(const char *channel) {
  if (strcmp(channel, "RED") == 0) {
    return &config.red_cal;
  }
  if (strcmp(channel, "GREEN") == 0) {
    return &config.green_cal;
  }
  if (strcmp(channel, "WHITE") == 0) {
    return &config.white_cal;
  }
  return nullptr;
}

const ChannelHardware *channelHardware(const char *channel) {
  for (uint8_t i = 0; i < kChannelCount; ++i) {
    if (strcmp(channel, kChannels[i].name) == 0) {
      return &kChannels[i];
    }
  }
  return nullptr;
}

const __FlashStringHelper *channelName(const char *channel) {
  if (strcmp(channel, "RED") == 0) {
    return F("RED");
  }
  if (strcmp(channel, "GREEN") == 0) {
    return F("GREEN");
  }
  if (strcmp(channel, "WHITE") == 0) {
    return F("WHITE");
  }
  return F("UNKNOWN");
}

void handleSet(char *cursor) {
  char *channel = nextToken(&cursor);
  if (channel == nullptr) {
    Serial.println(F("ERR SET requires channel"));
    return;
  }

  if (strcmp(channel, "ALL") == 0) {
    uint8_t red = 0;
    uint8_t green = 0;
    uint8_t white = 0;
    if (!parseByte(nextToken(&cursor), &red) ||
        !parseByte(nextToken(&cursor), &green) ||
        !parseByte(nextToken(&cursor), &white)) {
      Serial.println(F("ERR SET ALL requires three 0-255 values"));
      return;
    }

    config.red = red;
    config.green = green;
    config.white = white;
    commitLiveOutputs();

    if (isSaveToken(nextToken(&cursor))) {
      saveConfig();
      return;
    }
    printConfig(F("OK SET"));
    return;
  }

  uint8_t value = 0;
  if (!parseByte(nextToken(&cursor), &value)) {
    Serial.println(F("ERR SET requires 0-255 value"));
    return;
  }

  if (strcmp(channel, "RED") == 0) {
    config.red = value;
  } else if (strcmp(channel, "GREEN") == 0) {
    config.green = value;
  } else if (strcmp(channel, "WHITE") == 0) {
    config.white = value;
  } else {
    Serial.println(F("ERR unknown channel"));
    return;
  }

  commitLiveOutputs();

  if (isSaveToken(nextToken(&cursor))) {
    saveConfig();
    return;
  }
  printConfig(F("OK SET"));
}

void handleSetCalibrated(char *cursor) {
  char *channel = nextToken(&cursor);
  if (channel == nullptr) {
    Serial.println(F("ERR SETC requires channel"));
    return;
  }

  if (strcmp(channel, "ALL") == 0) {
    uint8_t red = 0;
    uint8_t green = 0;
    uint8_t white = 0;
    if (!parseByte(nextToken(&cursor), &red) ||
        !parseByte(nextToken(&cursor), &green) ||
        !parseByte(nextToken(&cursor), &white)) {
      Serial.println(F("ERR SETC ALL requires three 0-255 values"));
      return;
    }

    config.red = calibratedToPwm(config.red_cal, red);
    config.green = calibratedToPwm(config.green_cal, green);
    config.white = calibratedToPwm(config.white_cal, white);
    commitLiveOutputs();

    if (isSaveToken(nextToken(&cursor))) {
      saveConfig();
      return;
    }
    printConfig(F("OK SETC"));
    return;
  }

  uint8_t brightness = 0;
  if (!parseByte(nextToken(&cursor), &brightness)) {
    Serial.println(F("ERR SETC requires 0-255 value"));
    return;
  }

  uint8_t *value = channelValue(channel);
  ChannelCalibration *cal = channelCalibration(channel);
  if (value == nullptr || cal == nullptr) {
    Serial.println(F("ERR unknown channel"));
    return;
  }

  *value = calibratedToPwm(*cal, brightness);
  commitLiveOutputs();

  if (isSaveToken(nextToken(&cursor))) {
    saveConfig();
    return;
  }
  printConfig(F("OK SETC"));
}

void handleCal(char *cursor) {
  char *subcommand = nextToken(&cursor);
  if (subcommand == nullptr || strcmp(subcommand, "GET") == 0) {
    printCalibration(F("OK CAL"));
    return;
  }

  if (strcmp(subcommand, "SET") == 0) {
    char *channel = nextToken(&cursor);
    ChannelCalibration *cal = channel == nullptr ? nullptr : channelCalibration(channel);
    if (cal == nullptr) {
      Serial.println(F("ERR CAL SET requires channel"));
      return;
    }

    uint8_t min_pwm = 0;
    uint8_t max_pwm = 0;
    if (!parseByte(nextToken(&cursor), &min_pwm) ||
        !parseByte(nextToken(&cursor), &max_pwm) ||
        max_pwm <= min_pwm) {
      Serial.println(F("ERR CAL SET requires min_pwm < max_pwm"));
      return;
    }

    char *maybe_threshold = nextToken(&cursor);
    uint16_t threshold = cal->threshold_ma_x100;
    char *maybe_save = maybe_threshold;
    if (maybe_threshold != nullptr && !isSaveToken(maybe_threshold)) {
      if (!parseUInt16(maybe_threshold, &threshold)) {
        Serial.println(F("ERR CAL SET threshold must be 0-65535"));
        return;
      }
      maybe_save = nextToken(&cursor);
    }

    cal->min_pwm = min_pwm;
    cal->max_pwm = max_pwm;
    cal->threshold_ma_x100 = threshold;
    refreshChecksum();

    if (isSaveToken(maybe_save)) {
      saveCalibrationConfig();
      return;
    }
    printCalibration(F("OK CAL SET"));
    return;
  }

  if (strcmp(subcommand, "FIND") == 0) {
    char *channel = nextToken(&cursor);
    ChannelCalibration *cal = channel == nullptr ? nullptr : channelCalibration(channel);
    uint8_t *value = channel == nullptr ? nullptr : channelValue(channel);
    const ChannelHardware *hardware = channel == nullptr ? nullptr : channelHardware(channel);
    if (cal == nullptr || value == nullptr || hardware == nullptr) {
      Serial.println(F("ERR CAL FIND requires channel"));
      return;
    }

    char *args[3] = {nullptr, nullptr, nullptr};
    uint8_t arg_count = 0;
    bool save_requested = false;
    char *token = nullptr;
    while ((token = nextToken(&cursor)) != nullptr) {
      if (isSaveToken(token)) {
        save_requested = true;
      } else if (arg_count < 3) {
        args[arg_count++] = token;
      } else {
        Serial.println(F("ERR CAL FIND too many arguments"));
        return;
      }
    }

    uint16_t threshold = cal->threshold_ma_x100;
    if (arg_count >= 1) {
      if (!parseUInt16(args[0], &threshold)) {
        Serial.println(F("ERR CAL FIND threshold must be 0-65535"));
        return;
      }
    }

    uint8_t delay_ms = kDefaultCalFindDelayMs;
    if (arg_count >= 2) {
      if (!parseByte(args[1], &delay_ms)) {
        Serial.println(F("ERR CAL FIND delay_ms must be 0-255"));
        return;
      }
    }

    uint8_t max_pwm = cal->max_pwm < kDefaultCalFindMaxPwm
                          ? cal->max_pwm
                          : kDefaultCalFindMaxPwm;
    if (arg_count >= 3) {
      if (!parseByte(args[2], &max_pwm) || max_pwm == 0) {
        Serial.println(F("ERR CAL FIND max_pwm must be 1-255"));
        return;
      }
    }

    const uint8_t original = *value;
    bool found = false;
    bool saturated = false;
    uint8_t found_pwm = 0;
    uint16_t found_current = 0;
    for (uint16_t pwm = 1; pwm <= max_pwm; ++pwm) {
      *value = static_cast<uint8_t>(pwm);
      refreshChecksum();
      applyOutputs();
      delay(delay_ms);
      const uint16_t adc = readAveragedAdc(hardware->sense_pin);
      if (adc >= kAdcSaturationCount) {
        saturated = true;
        break;
      }
      const uint16_t current =
          millivoltsToCentiamps(adcToMillivolts(adc), hardware->sense_resistor_milliohm);
      if (current >= threshold) {
        found = true;
        found_pwm = static_cast<uint8_t>(pwm);
        found_current = current;
        break;
      }
    }

    *value = original;
    refreshChecksum();
    applyOutputs();

    if (saturated) {
      Serial.println(F("ERR CAL FIND adc saturated"));
      return;
    }

    if (!found) {
      Serial.println(F("ERR CAL FIND threshold not reached"));
      return;
    }

    cal->min_pwm = found_pwm;
    cal->threshold_ma_x100 = threshold;
    if (cal->max_pwm <= cal->min_pwm) {
      cal->max_pwm = 255;
    }
    refreshChecksum();

    Serial.print(F("OK CAL FIND "));
    Serial.print(channelName(channel));
    Serial.print(F("_MIN_PWM="));
    Serial.print(found_pwm);
    Serial.print(F(" "));
    Serial.print(channelName(channel));
    Serial.print(F("_MA_X100="));
    Serial.print(found_current);
    Serial.print(F(" THRESHOLD_MA_X100="));
    Serial.print(threshold);
    Serial.print(F(" MAX_PWM="));
    Serial.println(max_pwm);

    if (save_requested) {
      saveCalibrationConfig();
    }
    return;
  }

  if (strcmp(subcommand, "RESET") == 0) {
    config.red_cal = {1, 255, kDefaultThresholdMaX100};
    config.green_cal = {1, 255, kDefaultThresholdMaX100};
    config.white_cal = {1, 255, kDefaultThresholdMaX100};
    refreshChecksum();
    if (isSaveToken(nextToken(&cursor))) {
      saveCalibrationConfig();
      return;
    }
    printCalibration(F("OK CAL RESET"));
    return;
  }

  Serial.println(F("ERR unknown CAL command"));
}

void handleCommand(char *line) {
  for (char *p = line; *p != '\0'; ++p) {
    *p = toupper(*p);
  }

  char *cursor = line;
  char *command = nextToken(&cursor);
  if (command == nullptr) {
    return;
  }

  if (strcmp(command, "PING") == 0) {
    Serial.println(F("OK PONG"));
  } else if (strcmp(command, "HELP") == 0) {
    printHelp();
  } else if (strcmp(command, "HARDWARE") == 0) {
    printHardwareSummary();
  } else if (strcmp(command, "GET") == 0) {
    printConfig(F("OK"));
  } else if (strcmp(command, "GETCAL") == 0) {
    printCalibration(F("OK CAL"));
  } else if (strcmp(command, "SENSE") == 0) {
    handleSense(cursor);
  } else if (strcmp(command, "SET") == 0) {
    handleSet(cursor);
  } else if (strcmp(command, "SETC") == 0) {
    handleSetCalibrated(cursor);
  } else if (strcmp(command, "CAL") == 0) {
    handleCal(cursor);
  } else if (strcmp(command, "ZERO") == 0) {
    config.red = 0;
    config.green = 0;
    config.white = 0;
    commitLiveOutputs();
    if (isSaveToken(nextToken(&cursor))) {
      saveConfig();
      return;
    }
    printConfig(F("OK ZERO"));
  } else if (strcmp(command, "SAVE") == 0) {
    saveConfig();
  } else if (strcmp(command, "LOAD") == 0) {
    loadConfig();
  } else if (strcmp(command, "DEFAULTS") == 0) {
    setDefaults();
    commitLiveOutputs();
    printConfig(F("OK DEFAULTS"));
  } else {
    Serial.println(F("ERR unknown command"));
  }
}

void processSerial() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      lineBuffer[lineLength] = '\0';
      handleCommand(lineBuffer);
      lineLength = 0;
      return;
    }

    if (lineLength < sizeof(lineBuffer) - 1) {
      lineBuffer[lineLength++] = c;
    } else {
      lineLength = 0;
      Serial.println(F("ERR line too long"));
    }
  }
}

void setupHighFrequencyPwm() {
  for (uint8_t i = 0; i < kChannelCount; ++i) {
    pinMode(kChannels[i].pwm_pin, OUTPUT);
    digitalWrite(kChannels[i].pwm_pin, LOW);
  }

  OCR1A = 0;
  OCR1B = 0;
  OCR2B = 0;

  TCCR1A = _BV(COM1A1) | _BV(COM1B1) | _BV(WGM10);
  TCCR1B = _BV(WGM12) | _BV(CS10);

  TCCR2A = _BV(COM2B1) | _BV(WGM21) | _BV(WGM20);
  TCCR2B = _BV(CS20);
}

}  // namespace

void setup() {
  setupHighFrequencyPwm();
  analogReference(INTERNAL);

  Serial.begin(kBaudRate);
  loadStartupConfig();
}

void loop() {
  processSerial();
}
