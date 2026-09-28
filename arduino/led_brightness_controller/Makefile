ARDUINO_DIR = /usr/share/arduino
ARDMK_DIR = /usr/share/arduino
BOARD_TAG = nano328
BOARD_SUB =
MONITOR_BAUDRATE = 115200
CPPFLAGS += -DDECIMAL_DIG=9

ifneq ($(MAKECMDGOALS),host-test)
include /usr/share/arduino/Arduino.mk
endif

HOST_CXX ?= g++
HOST_TEST = tests/safe_current_contract_test

.PHONY: host-test
host-test:
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -pedantic -o $(HOST_TEST) tests/safe_current_contract_test.cpp
	./$(HOST_TEST)
	rm -f $(HOST_TEST)
