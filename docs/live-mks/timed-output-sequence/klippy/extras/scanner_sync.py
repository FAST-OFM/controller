# Scanner synchronization timed-output bench support.
#
# This live Klipper extra keeps the current MKS pin config shape and adds a
# generic MCU-timed sequence command for no-motion LED/XVS diagnostics. It does
# not command motors, home axes, flash firmware, or change LED brightness.

import binascii
import struct


class ScannerSync:
    OUTPUT_LED_WHITE = 0x01
    OUTPUT_LED_RED = 0x02
    OUTPUT_LED_GREEN = 0x04
    OUTPUT_HQ_XVS_SYNC = 0x08
    KNOWN_OUTPUT_MASK = (
        OUTPUT_LED_WHITE | OUTPUT_LED_RED | OUTPUT_LED_GREEN | OUTPUT_HQ_XVS_SYNC
    )
    TIMED_STEP_BYTES = 10
    MAX_STEPS = 12
    MAX_ENCODED_STEPS_BYTES = 120
    MAX_STEP_DELAY_US = 100000
    KNOWN_EVENT_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0008 | 0x0010 | 0x0020

    cmd_SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE_help = (
        "Run a no-motion MCU-timed LED/XVS output sequence")
    cmd_SCANNER_SYNC_TIMED_OUTPUT_STOP_help = (
        "Stop the active scanner-sync timed output sequence and apply safe state")
    cmd_SCANNER_SYNC_AF_WINDOW_TEST_help = (
        "Run the no-motion MCU-timed AF light/XVS window train")
    cmd_SCANNER_SYNC_AF_WINDOW_STOP_help = (
        "Stop legacy scanner-sync AF window test and set outputs inactive")

    def __init__(self, config):
        self.printer = config.get_printer()
        self.enabled = config.getboolean("enable", False)
        self.protocol_version = config.getint("protocol_version", 1, minval=1, maxval=1)
        self.status = "disabled"
        self.commands = {}
        self.last_test = None
        self.last_status = None
        self.last_frame_event = None
        self.frame_events = []
        self.frame_event_limit = config.getint("frame_event_limit", 256, minval=1, maxval=4096)
        self.allow_generic_timed_output_sequence = config.getboolean(
            "allow_generic_timed_output_sequence", False)
        self.next_seq = 1
        self.oid = None
        if not self.enabled:
            return
        self.mcu = self.printer.lookup_object(config.get("mcu", "mcu"))
        self.oid = self.mcu.create_oid()
        self.cmd_queue = self.mcu.alloc_command_queue()
        self.white_pin = config.get("white_pin", config.get("led_white_pin", None))
        self.red_pin = config.get("red_pin", config.get("led_red_pin", None))
        self.green_pin = config.get("green_pin", config.get("led_green_pin", None))
        self.xvs_pin = config.get("xvs_pin", config.get("hq_xvs_sync_pin", None))
        self.mcu.register_config_callback(self._build_config)
        gcode = self.printer.lookup_object("gcode")
        if self.allow_generic_timed_output_sequence:
            gcode.register_command("SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE",
                                   self.cmd_SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE,
                                   desc=self.cmd_SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE_help)
            gcode.register_command("SCANNER_SYNC_TIMED_OUTPUT_STOP",
                                   self.cmd_SCANNER_SYNC_TIMED_OUTPUT_STOP,
                                   desc=self.cmd_SCANNER_SYNC_TIMED_OUTPUT_STOP_help)
        gcode.register_command("SCANNER_SYNC_AF_WINDOW_TEST",
                               self.cmd_SCANNER_SYNC_AF_WINDOW_TEST,
                               desc=self.cmd_SCANNER_SYNC_AF_WINDOW_TEST_help)
        gcode.register_command("SCANNER_SYNC_AF_WINDOW_STOP",
                               self.cmd_SCANNER_SYNC_AF_WINDOW_STOP,
                               desc=self.cmd_SCANNER_SYNC_AF_WINDOW_STOP_help)
        self.status = "configured"

    def _build_config(self):
        self.mcu.add_config_cmd(
            "config_scanner_sync_outputs oid=%d white_pin=%s red_pin=%s"
            " green_pin=%s xvs_pin=%s" % (
                self.oid, self.white_pin, self.red_pin, self.green_pin, self.xvs_pin))
        self.commands["begin_timed_output_sequence"] = self.mcu.lookup_command(
            "scanner_sync_begin_timed_output_sequence oid=%c seq=%u"
            " stripe_id=%u seq_id=%u mode=%c start_condition=%c"
            " start_position_count=%i repeat_count=%u frame_id_base=%i"
            " pattern_id=%u safe_output_mask=%c safe_output_values=%c"
            " idle_output_mask=%c idle_output_values=%c expected_step_count=%u",
            cq=self.cmd_queue)
        self.commands["add_timed_output_step"] = self.mcu.lookup_command(
            "scanner_sync_add_timed_output_step oid=%c step_index=%u"
            " output_mask=%c output_values=%c pattern_id=%u delay_us=%u"
            " event_flags=%u",
            cq=self.cmd_queue)
        self.commands["start_timed_output_sequence"] = self.mcu.lookup_command(
            "scanner_sync_start_timed_output_sequence oid=%c",
            cq=self.cmd_queue)
        self.commands["stop"] = self.mcu.lookup_command(
            "scanner_sync_stop oid=%c reason=%c", cq=self.cmd_queue)
        self.commands["af_window_test"] = self.mcu.lookup_command(
            "scanner_sync_af_window_test oid=%c cycles=%u period_us=%u"
            " white_pre_us=%u white_to_rg_us=%u rg_settle_us=%u"
            " xvs_pulse_us=%u exposure_hold_us=%u rg_to_white_us=%u"
            " end_white=%c seq=%u stripe_id=%u frame_id_base=%i"
            " pattern_id=%u emit_frame_events=%c",
            cq=self.cmd_queue)
        self.commands["af_window_stop"] = self.mcu.lookup_command(
            "scanner_sync_af_window_stop oid=%c", cq=self.cmd_queue)
        self.mcu.register_serial_response(
            self._handle_frame_event,
            "scanner_sync_frame_event oid=%c frame_id=%u stripe_id=%u"
            " stripe_frame_index=%u pattern_id=%u position_axis=%c"
            " event_position=%i x_count=%i y_count=%i z_count=%i"
            " mcu_time_us=%u status=%c flags=%u", self.oid)
        self.mcu.register_serial_response(
            self._handle_timed_output_status,
            "scanner_sync_timed_output_sequence_status oid=%c seq=%u stripe_id=%u"
            " seq_id=%u status=%c reason=%c repeat_index=%u step_index=%u"
            " mcu_time_us=%u", self.oid)

    def get_status(self, eventtime):
        return {
            "enabled": self.enabled,
            "status": self.status,
            "last_test": self.last_test,
            "last_status": self.last_status,
            "last_frame_event": self.last_frame_event,
            "frame_events": list(self.frame_events),
            "frame_event_count": len(self.frame_events),
            "allow_generic_timed_output_sequence": self.allow_generic_timed_output_sequence,
        }

    def _handle_frame_event(self, params):
        event = dict(params)
        self.last_frame_event = event
        self.frame_events.append(event)
        if len(self.frame_events) > self.frame_event_limit:
            self.frame_events = self.frame_events[-self.frame_event_limit:]

    def _handle_timed_output_status(self, params):
        self.last_status = dict(params)

    def _require_enabled(self, gcmd):
        if not self.enabled or self.oid is None:
            raise gcmd.error("[scanner_sync] must be enabled for this command")

    def _get_us(self, gcmd, name, default, minval=0):
        return gcmd.get_int(name, default, minval=minval)

    def _next_sequence_number(self, explicit):
        if explicit is not None:
            self.next_seq = explicit + 1
            return explicit
        seq = self.next_seq
        self.next_seq += 1
        return seq

    def _decode_steps_hex(self, gcmd):
        value = gcmd.get("STEPS_HEX", "").strip()
        if not value:
            raise gcmd.error("STEPS_HEX is required")
        try:
            encoded = binascii.unhexlify(value)
        except (TypeError, binascii.Error) as exc:
            raise gcmd.error("STEPS_HEX must be even-length hexadecimal") from exc
        if len(encoded) > self.MAX_ENCODED_STEPS_BYTES:
            raise gcmd.error(
                "STEPS_HEX encoded payload must be <= %d bytes"
                % self.MAX_ENCODED_STEPS_BYTES
            )
        if len(encoded) % self.TIMED_STEP_BYTES:
            raise gcmd.error(
                "STEPS_HEX length must be a multiple of %d bytes"
                % self.TIMED_STEP_BYTES
            )
        step_count = len(encoded) // self.TIMED_STEP_BYTES
        if step_count < 1 or step_count > self.MAX_STEPS:
            raise gcmd.error("STEPS_HEX must encode between 1 and %d steps" % self.MAX_STEPS)
        for step_index in range(step_count):
            offset = step_index * self.TIMED_STEP_BYTES
            output_mask = encoded[offset]
            output_values = encoded[offset + 1]
            reserved = encoded[offset + 3]
            delay_us = struct.unpack_from("<I", encoded, offset + 4)[0]
            event_flags = struct.unpack_from("<H", encoded, offset + 8)[0]
            if output_mask & ~self.KNOWN_OUTPUT_MASK:
                raise gcmd.error("STEPS_HEX step %d output mask has unknown bits" % step_index)
            if output_values & ~output_mask:
                raise gcmd.error(
                    "STEPS_HEX step %d output values set bits outside mask" % step_index
                )
            if reserved:
                raise gcmd.error("STEPS_HEX step %d reserved byte must be zero" % step_index)
            if delay_us > self.MAX_STEP_DELAY_US:
                raise gcmd.error(
                    "STEPS_HEX step %d delay_us must be <= %d"
                    % (step_index, self.MAX_STEP_DELAY_US)
                )
            if event_flags & ~self.KNOWN_EVENT_FLAGS:
                raise gcmd.error("STEPS_HEX step %d event flags have unknown bits" % step_index)
        return encoded, step_count

    def cmd_SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE(self, gcmd):
        self._require_enabled(gcmd)
        if not self.allow_generic_timed_output_sequence:
            raise gcmd.error(
                "SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE is disabled; use "
                "SCANNER_SYNC_AF_WINDOW_TEST for current no-motion RG/XVS validation"
            )
        encoded_steps, step_count = self._decode_steps_hex(gcmd)
        seq = self._next_sequence_number(gcmd.get_int("SEQ", None, minval=1))
        stripe_id = gcmd.get_int("STRIPE_ID", 0, minval=0)
        seq_id = gcmd.get_int("SEQ_ID", seq, minval=1)
        repeat_count = gcmd.get_int("REPEAT_COUNT", 1, minval=0)
        frame_id_base = gcmd.get_int("FRAME_ID_BASE", -1, minval=-1)
        pattern_id = gcmd.get_int("PATTERN_ID", 0, minval=0, maxval=255)
        safe_mask = gcmd.get_int("SAFE_MASK", self.KNOWN_OUTPUT_MASK, minval=0, maxval=255)
        safe_values = gcmd.get_int("SAFE_VALUES", 0, minval=0, maxval=255)
        idle_mask = gcmd.get_int("IDLE_MASK", self.KNOWN_OUTPUT_MASK, minval=0, maxval=255)
        idle_values = gcmd.get_int("IDLE_VALUES", 0, minval=0, maxval=255)
        if (safe_mask | idle_mask) & ~self.KNOWN_OUTPUT_MASK:
            raise gcmd.error("output masks contain unknown bits")
        if safe_values & ~safe_mask:
            raise gcmd.error("SAFE_VALUES sets bits outside SAFE_MASK")
        if idle_values & ~idle_mask:
            raise gcmd.error("IDLE_VALUES sets bits outside IDLE_MASK")
        self.frame_events = []
        self.commands["begin_timed_output_sequence"].send([
            self.oid, seq, stripe_id, seq_id, 0, 0, -1, repeat_count,
            frame_id_base, pattern_id, safe_mask, safe_values, idle_mask,
            idle_values, step_count])
        for step_index in range(step_count):
            offset = step_index * self.TIMED_STEP_BYTES
            delay_us = struct.unpack_from("<I", encoded_steps, offset + 4)[0]
            event_flags = struct.unpack_from("<H", encoded_steps, offset + 8)[0]
            self.commands["add_timed_output_step"].send([
                self.oid,
                step_index,
                encoded_steps[offset],
                encoded_steps[offset + 1],
                encoded_steps[offset + 2],
                delay_us,
                event_flags,
            ])
        self.commands["start_timed_output_sequence"].send([self.oid])
        self.last_test = {
            "command": "SCANNER_SYNC_TIMED_OUTPUT_SEQUENCE",
            "seq": seq,
            "stripe_id": stripe_id,
            "seq_id": seq_id,
            "repeat_count": repeat_count,
            "frame_id_base": frame_id_base,
            "pattern_id": pattern_id,
            "safe_mask": safe_mask,
            "safe_values": safe_values,
            "idle_mask": idle_mask,
            "idle_values": idle_values,
            "step_count": step_count,
            "transport": "staged",
        }
        gcmd.respond_info("scanner_sync timed output sequence queued on MCU")

    def cmd_SCANNER_SYNC_TIMED_OUTPUT_STOP(self, gcmd):
        self._require_enabled(gcmd)
        if not self.allow_generic_timed_output_sequence:
            raise gcmd.error("SCANNER_SYNC_TIMED_OUTPUT_STOP is disabled")
        reason = gcmd.get_int("REASON", 4, minval=0, maxval=255)
        self.commands["stop"].send([self.oid, reason])
        self.last_test = None
        gcmd.respond_info("scanner_sync timed output sequence stopped")

    def cmd_SCANNER_SYNC_AF_WINDOW_TEST(self, gcmd):
        self._require_enabled(gcmd)
        cycles = gcmd.get_int("CYCLES", 10, minval=1, maxval=10000)
        period_us = self._get_us(gcmd, "PERIOD_US", 100000, minval=1)
        white_pre_us = self._get_us(gcmd, "WHITE_PRE_US", 10000)
        white_to_rg_us = self._get_us(gcmd, "WHITE_TO_RG_US", 0)
        rg_settle_us = self._get_us(gcmd, "RG_SETTLE_US", 1000)
        xvs_pulse_us = self._get_us(gcmd, "XVS_PULSE_US", 200, minval=1)
        exposure_hold_us = self._get_us(gcmd, "EXPOSURE_HOLD_US", 2000)
        rg_to_white_us = self._get_us(gcmd, "RG_TO_WHITE_US", 0)
        end_white = gcmd.get_int("END_WHITE", 0, minval=0, maxval=1)
        seq = self._next_sequence_number(gcmd.get_int("SEQ", None, minval=1))
        stripe_id = gcmd.get_int("STRIPE_ID", 0, minval=0)
        frame_id_base = gcmd.get_int("FRAME_ID_BASE", -1, minval=-1)
        pattern_id = gcmd.get_int("PATTERN_ID", 1, minval=0, maxval=255)
        emit_frame_events = gcmd.get_int("EMIT_FRAME_EVENTS", 0, minval=0, maxval=1)
        used_us = (white_pre_us + white_to_rg_us + rg_settle_us
                   + xvs_pulse_us + exposure_hold_us + rg_to_white_us)
        if used_us > period_us:
            raise gcmd.error("PERIOD_US is shorter than configured window timing")
        self.frame_events = []
        self.commands["af_window_test"].send([
            self.oid, cycles, period_us, white_pre_us, white_to_rg_us,
            rg_settle_us, xvs_pulse_us, exposure_hold_us, rg_to_white_us,
            end_white, seq, stripe_id, frame_id_base, pattern_id,
            emit_frame_events])
        self.last_test = {
            "command": "SCANNER_SYNC_AF_WINDOW_TEST",
            "seq": seq,
            "stripe_id": stripe_id,
            "frame_id_base": frame_id_base,
            "pattern_id": pattern_id,
            "emit_frame_events": bool(emit_frame_events),
            "cycles": cycles,
            "period_us": period_us,
            "white_pre_us": white_pre_us,
            "white_to_rg_us": white_to_rg_us,
            "rg_settle_us": rg_settle_us,
            "xvs_pulse_us": xvs_pulse_us,
            "exposure_hold_us": exposure_hold_us,
            "rg_to_white_us": rg_to_white_us,
            "rg_to_white_semantics": "post_exposure_rg_hold_before_white_restore",
            "end_white": end_white,
        }
        gcmd.respond_info("scanner_sync AF window test queued on MCU")

    def cmd_SCANNER_SYNC_AF_WINDOW_STOP(self, gcmd):
        self._require_enabled(gcmd)
        self.commands["af_window_stop"].send([self.oid])
        self.last_test = None
        gcmd.respond_info("scanner_sync AF window test stopped")


def load_config(config):
    return ScannerSync(config)
