// Scanner synchronization timed-output diagnostics.
//
// This MKS-hosted Klipper MCU module implements a no-motion timed output
// sequence for LED/XVS bench work. It switches only configured outputs and does
// not command steppers, home axes, capture images, or flash firmware.

#include "basecmd.h" // oid_alloc
#include "board/gpio.h" // gpio_out_setup, gpio_out_write
#include "board/irq.h" // irq_disable, irq_enable
#include "board/misc.h" // timer_from_us, timer_read_time
#include "command.h" // DECL_COMMAND
#include "sched.h" // DECL_SHUTDOWN, DECL_TASK, sched_add_timer, sched_del_timer

enum {
    SS_OUTPUT_LED_WHITE = 0x01,
    SS_OUTPUT_LED_RED = 0x02,
    SS_OUTPUT_LED_GREEN = 0x04,
    SS_OUTPUT_HQ_XVS_SYNC = 0x08,
    SS_KNOWN_OUTPUT_MASK = SS_OUTPUT_LED_WHITE | SS_OUTPUT_LED_RED
        | SS_OUTPUT_LED_GREEN | SS_OUTPUT_HQ_XVS_SYNC,
    SS_STEP_BYTES = 10,
    SS_MAX_STEPS = 12,
    SS_MAX_STEP_DELAY_US = 100000,
    SS_MODE_DIAGNOSTIC_IMMEDIATE = 0,
    SS_START_IMMEDIATE = 0,
    SS_EVENT_FRAME = 0x0001,
    SS_EVENT_XVS_RISING = 0x0002,
    SS_EVENT_XVS_FALLING = 0x0004,
    SS_EVENT_END = 0x0008,
    SS_EVENT_EXPOSURE_START = 0x0010,
    SS_EVENT_EXPOSURE_END = 0x0020,
    SS_KNOWN_EVENT_FLAGS = SS_EVENT_FRAME | SS_EVENT_XVS_RISING
        | SS_EVENT_XVS_FALLING | SS_EVENT_END | SS_EVENT_EXPOSURE_START
        | SS_EVENT_EXPOSURE_END,
    SS_STATUS_ACCEPTED = 0,
    SS_STATUS_REJECTED = 1,
    SS_STATUS_STARTED = 2,
    SS_STATUS_COMPLETED = 3,
    SS_STATUS_STOPPED = 4,
    SS_STATUS_FAULT = 5,
    SS_REASON_ACCEPTED = 0,
    SS_REASON_INVALID_COMMAND = 1,
    SS_REASON_STARTED = 2,
    SS_REASON_FINITE_COMPLETION = 3,
    SS_REASON_HOST_STOP = 4,
    SS_REASON_FAULT = 5,
    SS_STATUS_QUEUE_LEN = 8,
    SS_FRAME_EVENT_QUEUE_LEN = 32,
};

struct scanner_sync_timed_output_step {
    uint8_t output_mask, output_values, pattern_id;
    uint32_t delay_ticks;
    uint16_t event_flags;
};

struct scanner_sync_pending_status {
    uint32_t seq, stripe_id, seq_id, repeat_index, mcu_time_us;
    uint8_t status, reason, step_index;
};

struct scanner_sync_pending_frame_event {
    uint32_t frame_id, stripe_id, stripe_frame_index, mcu_time_us;
    uint16_t flags;
    uint8_t pattern_id, status;
};

struct scanner_sync {
    struct timer timer;
    struct gpio_out white_pin, red_pin, green_pin, xvs_pin;
    struct scanner_sync_timed_output_step steps[SS_MAX_STEPS];
    struct scanner_sync_pending_status status_queue[SS_STATUS_QUEUE_LEN];
    struct scanner_sync_pending_frame_event frame_event_queue[SS_FRAME_EVENT_QUEUE_LEN];
    uint32_t period_ticks, white_pre_ticks, white_to_rg_ticks;
    uint32_t rg_settle_ticks, xvs_pulse_ticks, exposure_hold_ticks;
    uint32_t rg_to_white_ticks;
    uint32_t seq, stripe_id, seq_id, frame_id_base;
    uint32_t repeat_count, repeat_index, event_frame_index, mcu_time_base;
    uint16_t cycles_remaining;
    uint8_t oid, step_count, step_index, running;
    uint8_t state, end_white, sequence_active, timer_active;
    uint8_t safe_output_mask, safe_output_values;
    uint8_t idle_output_mask, idle_output_values, pattern_id;
    uint8_t emit_af_frame_events;
    uint8_t status_head, status_count, frame_event_head, frame_event_count;
    uint8_t staged_step_count, staged_ready;
};

static struct task_wake scanner_sync_wake;

enum {
    SS_WHITE_PRE = 0, SS_WHITE_TO_RG = 1, SS_RG_SETTLE = 2, SS_XVS_HIGH = 3,
    SS_EXPOSURE = 4, SS_RG_TO_WHITE = 5, SS_RESTORE_WHITE = 6, SS_IDLE = 7,
    SS_TIMED_SEQUENCE = 8
};

void command_config_scanner_sync_outputs(uint32_t *args);

static uint32_t
scanner_sync_clock_to_us(uint32_t clock)
{
    return clock / timer_from_us(1);
}

static uint32_t
scanner_sync_elapsed_us(struct scanner_sync *ss)
{
    return scanner_sync_clock_to_us(timer_read_time() - ss->mcu_time_base);
}

static uint16_t
scanner_sync_read_u16_le(const uint8_t *data)
{
    return data[0] | ((uint16_t)data[1] << 8);
}

static uint32_t
scanner_sync_read_u32_le(const uint8_t *data)
{
    return data[0] | ((uint32_t)data[1] << 8)
        | ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
}

static uint32_t
scanner_sync_crc32(const uint8_t *data, uint16_t len)
{
    uint32_t crc = 0xffffffff;
    uint16_t i;
    for (i = 0; i < len; i++) {
        crc ^= data[i];
        uint8_t bit;
        for (bit = 0; bit < 8; bit++) {
            uint32_t mask = -(crc & 1);
            crc = (crc >> 1) ^ (0xedb88320 & mask);
        }
    }
    return ~crc;
}

static struct scanner_sync *
scanner_sync_oid_lookup(uint8_t oid)
{
    return oid_lookup(oid, command_config_scanner_sync_outputs);
}

static void
scanner_sync_write_logical(struct scanner_sync *ss, uint8_t output_bit, uint8_t active)
{
    switch (output_bit) {
    case SS_OUTPUT_LED_WHITE:
        gpio_out_write(ss->white_pin, active);
        break;
    case SS_OUTPUT_LED_RED:
        gpio_out_write(ss->red_pin, active);
        break;
    case SS_OUTPUT_LED_GREEN:
        gpio_out_write(ss->green_pin, active);
        break;
    case SS_OUTPUT_HQ_XVS_SYNC:
        gpio_out_write(ss->xvs_pin, active);
        break;
    }
}

static void
scanner_sync_apply_output_state(struct scanner_sync *ss, uint8_t output_mask,
                                uint8_t output_values)
{
    uint8_t bit;
    for (bit = 1; bit <= SS_OUTPUT_HQ_XVS_SYNC; bit <<= 1) {
        if (output_mask & bit)
            scanner_sync_write_logical(ss, bit, !!(output_values & bit));
    }
}

static void
scanner_sync_outputs_safe(struct scanner_sync *ss)
{
    scanner_sync_apply_output_state(ss, SS_KNOWN_OUTPUT_MASK, 0);
}

static void
scanner_sync_clear_telemetry_queues(struct scanner_sync *ss)
{
    ss->status_head = 0;
    ss->status_count = 0;
    ss->frame_event_head = 0;
    ss->frame_event_count = 0;
}

static void
scanner_sync_stop_timer(struct scanner_sync *ss)
{
    if (ss->timer_active) {
        sched_del_timer(&ss->timer);
        ss->timer_active = 0;
    }
}

static void
scanner_sync_apply_safe_stop(struct scanner_sync *ss)
{
    scanner_sync_stop_timer(ss);
    scanner_sync_outputs_safe(ss);
    ss->sequence_active = 0;
    ss->running = 0;
}

static void
scanner_sync_send_timed_sequence_status(struct scanner_sync *ss, uint8_t status,
                                        uint8_t reason, uint32_t repeat_index,
                                        uint8_t step_index, uint32_t mcu_time_us)
{
    sendf("scanner_sync_timed_output_sequence_status oid=%c seq=%u stripe_id=%u"
          " seq_id=%u status=%c reason=%c repeat_index=%u step_index=%u"
          " mcu_time_us=%u",
          ss->oid, ss->seq, ss->stripe_id, ss->seq_id, status, reason,
          repeat_index, step_index, mcu_time_us);
}

static void
scanner_sync_emit_timed_sequence_status(struct scanner_sync *ss, uint8_t status,
                                        uint8_t reason)
{
    uint32_t mcu_time_us = ss->mcu_time_base
        ? scanner_sync_elapsed_us(ss) : 0;
    scanner_sync_send_timed_sequence_status(
        ss, status, reason, ss->repeat_index, ss->step_index,
        mcu_time_us);
}

static void
scanner_sync_queue_timed_sequence_status(struct scanner_sync *ss, uint8_t status,
                                         uint8_t reason)
{
    if (ss->status_count >= SS_STATUS_QUEUE_LEN) {
        ss->status_head = (ss->status_head + 1) % SS_STATUS_QUEUE_LEN;
        ss->status_count--;
    }
    uint8_t index = (ss->status_head + ss->status_count) % SS_STATUS_QUEUE_LEN;
    struct scanner_sync_pending_status *pending = &ss->status_queue[index];
    pending->seq = ss->seq;
    pending->stripe_id = ss->stripe_id;
    pending->seq_id = ss->seq_id;
    pending->status = status;
    pending->reason = reason;
    pending->repeat_index = ss->repeat_index;
    pending->step_index = ss->step_index;
    pending->mcu_time_us = scanner_sync_elapsed_us(ss);
    ss->status_count++;
    sched_wake_task(&scanner_sync_wake);
}

static void
scanner_sync_emit_timed_sequence_rejected(uint8_t oid, uint32_t seq,
                                          uint32_t stripe_id, uint32_t seq_id)
{
    sendf("scanner_sync_timed_output_sequence_status oid=%c seq=%u stripe_id=%u"
          " seq_id=%u status=%c reason=%c repeat_index=%u step_index=%u"
          " mcu_time_us=%u",
          oid, seq, stripe_id, seq_id, SS_STATUS_REJECTED,
          SS_REASON_INVALID_COMMAND, 0, 0,
          scanner_sync_clock_to_us(timer_read_time()));
}

static void
scanner_sync_queue_frame_event_at(struct scanner_sync *ss, uint16_t event_flags,
                                  uint32_t frame_index, uint8_t pattern_id)
{
    if (ss->frame_event_count >= SS_FRAME_EVENT_QUEUE_LEN) {
        ss->frame_event_head = (
            ss->frame_event_head + 1) % SS_FRAME_EVENT_QUEUE_LEN;
        ss->frame_event_count--;
    }
    uint8_t index = (
        ss->frame_event_head + ss->frame_event_count) % SS_FRAME_EVENT_QUEUE_LEN;
    struct scanner_sync_pending_frame_event *pending = &ss->frame_event_queue[index];
    pending->frame_id = ss->frame_id_base == (uint32_t)-1
        ? frame_index : ss->frame_id_base + frame_index;
    pending->stripe_id = ss->stripe_id;
    pending->stripe_frame_index = frame_index;
    pending->pattern_id = pattern_id;
    pending->mcu_time_us = scanner_sync_elapsed_us(ss);
    pending->status = 0;
    pending->flags = event_flags;
    ss->frame_event_count++;
    sched_wake_task(&scanner_sync_wake);
}

static uint8_t
scanner_sync_decode_timed_output_step(struct scanner_sync_timed_output_step *step,
                                      const uint8_t *encoded)
{
    uint32_t delay_us;
    step->output_mask = encoded[0];
    step->output_values = encoded[1];
    step->pattern_id = encoded[2];
    if (encoded[3])
        return 0;
    delay_us = scanner_sync_read_u32_le(encoded + 4);
    if (delay_us > SS_MAX_STEP_DELAY_US)
        return 0;
    step->delay_ticks = timer_from_us(delay_us);
    step->event_flags = scanner_sync_read_u16_le(encoded + 8);
    if ((step->output_mask & ~SS_KNOWN_OUTPUT_MASK)
        || (step->output_values & ~step->output_mask)
        || (step->event_flags & ~SS_KNOWN_EVENT_FLAGS))
        return 0;
    return 1;
}

static uint32_t
scanner_sync_idle_ticks(struct scanner_sync *ss)
{
    uint32_t used = ss->white_pre_ticks + ss->white_to_rg_ticks
        + ss->rg_settle_ticks + ss->xvs_pulse_ticks + ss->exposure_hold_ticks
        + ss->rg_to_white_ticks;
    return ss->period_ticks - used;
}

static uint_fast8_t
scanner_sync_timer_event(struct timer *timer)
{
    struct scanner_sync *ss = container_of(timer, struct scanner_sync, timer);
    uint8_t guard = 0;
    for (;;) {
        uint32_t delay = 0;
        switch (ss->state) {
        case SS_TIMED_SEQUENCE: {
            if (!ss->sequence_active || ss->step_index >= ss->step_count) {
                scanner_sync_queue_timed_sequence_status(ss, SS_STATUS_FAULT,
                                                         SS_REASON_FAULT);
                scanner_sync_outputs_safe(ss);
                ss->sequence_active = 0;
                ss->timer_active = 0;
                return SF_DONE;
            }
            struct scanner_sync_timed_output_step *step = &ss->steps[ss->step_index];
            if (step->output_mask)
                scanner_sync_apply_output_state(ss, step->output_mask,
                                                step->output_values);
            if (step->event_flags & SS_EVENT_FRAME)
                scanner_sync_queue_frame_event_at(
                    ss, step->event_flags, ss->event_frame_index++,
                    step->pattern_id ? step->pattern_id : ss->pattern_id);
            delay = step->delay_ticks;
            ss->step_index++;
            if (ss->step_index >= ss->step_count) {
                ss->step_index = 0;
                ss->repeat_index++;
                if (ss->repeat_count && ss->repeat_index >= ss->repeat_count) {
                    scanner_sync_apply_output_state(ss, ss->idle_output_mask,
                                                    ss->idle_output_values);
                    scanner_sync_queue_timed_sequence_status(
                        ss, SS_STATUS_COMPLETED, SS_REASON_FINITE_COMPLETION);
                    ss->sequence_active = 0;
                    ss->timer_active = 0;
                    ss->running = 0;
                    return SF_DONE;
                }
            }
            break;
        }
        case SS_WHITE_PRE:
            gpio_out_write(ss->white_pin, 1);
            gpio_out_write(ss->green_pin, 0);
            gpio_out_write(ss->red_pin, 0);
            gpio_out_write(ss->xvs_pin, 0);
            ss->state = SS_WHITE_TO_RG;
            delay = ss->white_pre_ticks;
            break;
        case SS_WHITE_TO_RG:
            gpio_out_write(ss->white_pin, 0);
            ss->state = SS_RG_SETTLE;
            delay = ss->white_to_rg_ticks;
            break;
        case SS_RG_SETTLE:
            gpio_out_write(ss->green_pin, 1);
            gpio_out_write(ss->red_pin, 1);
            ss->state = SS_XVS_HIGH;
            delay = ss->rg_settle_ticks;
            break;
        case SS_XVS_HIGH:
            gpio_out_write(ss->xvs_pin, 1);
            if (ss->emit_af_frame_events)
                scanner_sync_queue_frame_event_at(
                    ss, SS_EVENT_FRAME | SS_EVENT_XVS_RISING
                    | SS_EVENT_EXPOSURE_START, ss->repeat_index,
                    ss->pattern_id);
            ss->state = SS_EXPOSURE;
            delay = ss->xvs_pulse_ticks;
            break;
        case SS_EXPOSURE:
            gpio_out_write(ss->xvs_pin, 0);
            ss->state = SS_RG_TO_WHITE;
            delay = ss->exposure_hold_ticks;
            break;
        case SS_RG_TO_WHITE:
            ss->state = SS_RESTORE_WHITE;
            delay = ss->rg_to_white_ticks;
            break;
        case SS_RESTORE_WHITE:
            gpio_out_write(ss->green_pin, 0);
            gpio_out_write(ss->red_pin, 0);
            gpio_out_write(ss->white_pin, 1);
            ss->state = SS_IDLE;
            break;
        case SS_IDLE:
            gpio_out_write(ss->white_pin, 1);
            ss->repeat_index++;
            if (!--ss->cycles_remaining) {
                gpio_out_write(ss->white_pin, ss->end_white);
                ss->running = 0;
                ss->timer_active = 0;
                return SF_DONE;
            }
            ss->state = SS_WHITE_PRE;
            delay = scanner_sync_idle_ticks(ss);
            break;
        default:
            scanner_sync_outputs_safe(ss);
            shutdown("scanner_sync invalid AF window state");
        }
        if (delay) {
            ss->timer.waketime += delay;
            return SF_RESCHEDULE;
        }
        if (++guard > 32)
            shutdown("scanner_sync zero-delay state loop");
    }
}

void
scanner_sync_task(void)
{
    if (!sched_check_wake(&scanner_sync_wake))
        return;
    uint8_t oid;
    struct scanner_sync *ss;
    foreach_oid(oid, ss, command_config_scanner_sync_outputs) {
        for (;;) {
            struct scanner_sync_pending_status pending;
            uint8_t has_pending = 0;
            irq_disable();
            if (ss->status_count) {
                pending = ss->status_queue[ss->status_head];
                ss->status_head = (ss->status_head + 1) % SS_STATUS_QUEUE_LEN;
                ss->status_count--;
                has_pending = 1;
            }
            irq_enable();
            if (!has_pending)
                break;
            sendf("scanner_sync_timed_output_sequence_status oid=%c seq=%u"
                  " stripe_id=%u seq_id=%u status=%c reason=%c"
                  " repeat_index=%u step_index=%u mcu_time_us=%u",
                  ss->oid, pending.seq, pending.stripe_id, pending.seq_id,
                  pending.status, pending.reason, pending.repeat_index,
                  pending.step_index, pending.mcu_time_us);
        }
        for (;;) {
            struct scanner_sync_pending_frame_event pending;
            uint8_t has_pending = 0;
            irq_disable();
            if (ss->frame_event_count) {
                pending = ss->frame_event_queue[ss->frame_event_head];
                ss->frame_event_head = (
                    ss->frame_event_head + 1) % SS_FRAME_EVENT_QUEUE_LEN;
                ss->frame_event_count--;
                has_pending = 1;
            }
            irq_enable();
            if (!has_pending)
                break;
            sendf("scanner_sync_frame_event oid=%c frame_id=%u stripe_id=%u"
                  " stripe_frame_index=%u pattern_id=%u position_axis=%c"
                  " event_position=%i x_count=%i y_count=%i z_count=%i"
                  " mcu_time_us=%u status=%c flags=%u",
                  ss->oid, pending.frame_id, pending.stripe_id,
                  pending.stripe_frame_index, pending.pattern_id, 'X',
                  0, 0, 0, 0, pending.mcu_time_us, pending.status,
                  pending.flags);
        }
    }
}
DECL_TASK(scanner_sync_task);

void
command_config_scanner_sync_outputs(uint32_t *args)
{
    struct scanner_sync *ss = oid_alloc(
        args[0], command_config_scanner_sync_outputs, sizeof(*ss));
    ss->oid = args[0];
    ss->white_pin = gpio_out_setup(args[1], 0);
    ss->red_pin = gpio_out_setup(args[2], 0);
    ss->green_pin = gpio_out_setup(args[3], 0);
    ss->xvs_pin = gpio_out_setup(args[4], 0);
    ss->timer.func = scanner_sync_timer_event;
    ss->safe_output_mask = SS_KNOWN_OUTPUT_MASK;
    ss->safe_output_values = 0;
    ss->idle_output_mask = SS_KNOWN_OUTPUT_MASK;
    ss->idle_output_values = 0;
    scanner_sync_outputs_safe(ss);
}
DECL_COMMAND(command_config_scanner_sync_outputs,
             "config_scanner_sync_outputs oid=%c white_pin=%u red_pin=%u"
             " green_pin=%u xvs_pin=%u");

void
command_scanner_sync_run_timed_output_sequence(uint32_t *args)
{
    uint8_t oid = args[0];
    struct scanner_sync *ss = scanner_sync_oid_lookup(oid);
    uint8_t mode = args[4], start_condition = args[5];
    uint8_t safe_mask = args[10], safe_values = args[11];
    uint8_t idle_mask = args[12], idle_values = args[13];
    uint8_t step_count = args[14];
    uint32_t steps_crc32 = args[15];
    uint16_t encoded_steps_len = args[16];
    const uint8_t *encoded_steps = command_decode_ptr(args[17]);

    if (ss->timer_active || mode != SS_MODE_DIAGNOSTIC_IMMEDIATE
        || start_condition != SS_START_IMMEDIATE || args[6] != (uint32_t)-1
        || step_count == 0 || step_count > SS_MAX_STEPS
        || encoded_steps_len != step_count * SS_STEP_BYTES
        || (safe_mask & ~SS_KNOWN_OUTPUT_MASK)
        || (safe_values & ~safe_mask)
        || (idle_mask & ~SS_KNOWN_OUTPUT_MASK)
        || (idle_values & ~idle_mask)
        || scanner_sync_crc32(encoded_steps, encoded_steps_len) != steps_crc32) {
        scanner_sync_outputs_safe(ss);
        scanner_sync_emit_timed_sequence_rejected(oid, args[1], args[2], args[3]);
        return;
    }

    uint8_t i;
    for (i = 0; i < step_count; i++) {
        if (!scanner_sync_decode_timed_output_step(
                &ss->steps[i], encoded_steps + i * SS_STEP_BYTES)) {
            scanner_sync_outputs_safe(ss);
            scanner_sync_emit_timed_sequence_rejected(oid, args[1], args[2], args[3]);
            return;
        }
    }

    irq_disable();
    ss->seq = args[1];
    ss->stripe_id = args[2];
    ss->seq_id = args[3];
    ss->repeat_count = args[7];
    ss->frame_id_base = args[8];
    ss->pattern_id = args[9];
    ss->emit_af_frame_events = 0;
    ss->safe_output_mask = safe_mask;
    ss->safe_output_values = safe_values;
    ss->idle_output_mask = idle_mask;
    ss->idle_output_values = idle_values;
    ss->step_count = step_count;
    ss->step_index = 0;
    ss->repeat_index = 0;
    ss->event_frame_index = 0;
    ss->state = SS_TIMED_SEQUENCE;
    ss->sequence_active = 1;
    ss->running = 1;
    ss->timer_active = 1;
    ss->mcu_time_base = timer_read_time();
    ss->timer.waketime = ss->mcu_time_base + timer_from_us(100);
    sched_add_timer(&ss->timer);
    irq_enable();
    scanner_sync_emit_timed_sequence_status(ss, SS_STATUS_ACCEPTED,
                                            SS_REASON_ACCEPTED);
    scanner_sync_emit_timed_sequence_status(ss, SS_STATUS_STARTED,
                                            SS_REASON_STARTED);
}
DECL_COMMAND(command_scanner_sync_run_timed_output_sequence,
             "scanner_sync_run_timed_output_sequence oid=%c seq=%u stripe_id=%u"
             " seq_id=%u mode=%c start_condition=%c start_position_count=%i"
             " repeat_count=%u frame_id_base=%i pattern_id=%u"
             " safe_output_mask=%c safe_output_values=%c idle_output_mask=%c"
             " idle_output_values=%c step_count=%u steps_crc32=%u"
             " encoded_steps=%*s");

void
command_scanner_sync_begin_timed_output_sequence(uint32_t *args)
{
    uint8_t oid = args[0];
    struct scanner_sync *ss = scanner_sync_oid_lookup(oid);
    uint8_t mode = args[4], start_condition = args[5];
    uint8_t safe_mask = args[10], safe_values = args[11];
    uint8_t idle_mask = args[12], idle_values = args[13];
    uint8_t expected_step_count = args[14];

    if (ss->timer_active || mode != SS_MODE_DIAGNOSTIC_IMMEDIATE
        || start_condition != SS_START_IMMEDIATE || args[6] != (uint32_t)-1
        || expected_step_count == 0 || expected_step_count > SS_MAX_STEPS
        || (safe_mask & ~SS_KNOWN_OUTPUT_MASK)
        || (safe_values & ~safe_mask)
        || (idle_mask & ~SS_KNOWN_OUTPUT_MASK)
        || (idle_values & ~idle_mask)) {
        scanner_sync_outputs_safe(ss);
        scanner_sync_emit_timed_sequence_rejected(oid, args[1], args[2], args[3]);
        return;
    }

    irq_disable();
    scanner_sync_stop_timer(ss);
    scanner_sync_outputs_safe(ss);
    scanner_sync_clear_telemetry_queues(ss);
    ss->seq = args[1];
    ss->stripe_id = args[2];
    ss->seq_id = args[3];
    ss->repeat_count = args[7];
    ss->frame_id_base = args[8];
    ss->pattern_id = args[9];
    ss->safe_output_mask = safe_mask;
    ss->safe_output_values = safe_values;
    ss->idle_output_mask = idle_mask;
    ss->idle_output_values = idle_values;
    ss->staged_step_count = expected_step_count;
    ss->step_count = 0;
    ss->step_index = 0;
    ss->repeat_index = 0;
    ss->event_frame_index = 0;
    ss->staged_ready = 1;
    ss->sequence_active = 0;
    ss->running = 0;
    irq_enable();
    scanner_sync_emit_timed_sequence_status(ss, SS_STATUS_ACCEPTED,
                                            SS_REASON_ACCEPTED);
}
DECL_COMMAND(command_scanner_sync_begin_timed_output_sequence,
             "scanner_sync_begin_timed_output_sequence oid=%c seq=%u"
             " stripe_id=%u seq_id=%u mode=%c start_condition=%c"
             " start_position_count=%i repeat_count=%u frame_id_base=%i"
             " pattern_id=%u safe_output_mask=%c safe_output_values=%c"
             " idle_output_mask=%c idle_output_values=%c expected_step_count=%u");

void
command_scanner_sync_add_timed_output_step(uint32_t *args)
{
    struct scanner_sync *ss = scanner_sync_oid_lookup(args[0]);
    uint8_t step_index = args[1];
    uint8_t output_mask = args[2], output_values = args[3];
    uint8_t pattern_id = args[4];
    uint32_t delay_us = args[5];
    uint16_t event_flags = args[6];

    if (!ss->staged_ready || ss->timer_active
        || step_index != ss->step_count || step_index >= ss->staged_step_count
        || delay_us > SS_MAX_STEP_DELAY_US
        || (output_mask & ~SS_KNOWN_OUTPUT_MASK)
        || (output_values & ~output_mask)
        || (event_flags & ~SS_KNOWN_EVENT_FLAGS)) {
        scanner_sync_outputs_safe(ss);
        scanner_sync_emit_timed_sequence_rejected(ss->oid, ss->seq,
                                                  ss->stripe_id, ss->seq_id);
        return;
    }

    struct scanner_sync_timed_output_step *step = &ss->steps[step_index];
    step->output_mask = output_mask;
    step->output_values = output_values;
    step->pattern_id = pattern_id;
    step->delay_ticks = timer_from_us(delay_us);
    step->event_flags = event_flags;
    ss->step_count++;
}
DECL_COMMAND(command_scanner_sync_add_timed_output_step,
             "scanner_sync_add_timed_output_step oid=%c step_index=%u"
             " output_mask=%c output_values=%c pattern_id=%u delay_us=%u"
             " event_flags=%u");

void
command_scanner_sync_start_timed_output_sequence(uint32_t *args)
{
    struct scanner_sync *ss = scanner_sync_oid_lookup(args[0]);
    if (!ss->staged_ready || ss->timer_active || !ss->step_count
        || ss->step_count != ss->staged_step_count) {
        scanner_sync_outputs_safe(ss);
        scanner_sync_emit_timed_sequence_rejected(ss->oid, ss->seq,
                                                  ss->stripe_id, ss->seq_id);
        return;
    }

    irq_disable();
    ss->step_index = 0;
    ss->repeat_index = 0;
    ss->event_frame_index = 0;
    ss->state = SS_TIMED_SEQUENCE;
    ss->sequence_active = 1;
    ss->running = 1;
    ss->timer_active = 1;
    ss->staged_ready = 0;
    ss->mcu_time_base = timer_read_time();
    ss->timer.waketime = ss->mcu_time_base + timer_from_us(100);
    sched_add_timer(&ss->timer);
    irq_enable();
    scanner_sync_emit_timed_sequence_status(ss, SS_STATUS_STARTED,
                                            SS_REASON_STARTED);
}
DECL_COMMAND(command_scanner_sync_start_timed_output_sequence,
             "scanner_sync_start_timed_output_sequence oid=%c");

void
command_scanner_sync_stop(uint32_t *args)
{
    struct scanner_sync *ss = scanner_sync_oid_lookup(args[0]);
    uint8_t was_sequence_active = ss->sequence_active;
    irq_disable();
    scanner_sync_apply_safe_stop(ss);
    irq_enable();
    if (was_sequence_active)
        scanner_sync_emit_timed_sequence_status(ss, SS_STATUS_STOPPED,
                                                SS_REASON_HOST_STOP);
}
DECL_COMMAND(command_scanner_sync_stop, "scanner_sync_stop oid=%c reason=%c");

void
command_scanner_sync_af_window_test(uint32_t *args)
{
    struct scanner_sync *ss = scanner_sync_oid_lookup(args[0]);
    uint32_t period_us = args[2];
    uint32_t white_pre_us = args[3], white_to_rg_us = args[4];
    uint32_t rg_settle_us = args[5], xvs_pulse_us = args[6];
    uint32_t exposure_hold_us = args[7], rg_to_white_us = args[8];
    uint32_t used_us = white_pre_us + white_to_rg_us + rg_settle_us
        + xvs_pulse_us + exposure_hold_us + rg_to_white_us;
    if (!args[1] || !period_us || !xvs_pulse_us || used_us > period_us)
        shutdown("invalid scanner_sync AF window test timing");

    irq_disable();
    scanner_sync_stop_timer(ss);
    scanner_sync_outputs_safe(ss);
    ss->period_ticks = timer_from_us(period_us);
    ss->white_pre_ticks = timer_from_us(white_pre_us);
    ss->white_to_rg_ticks = timer_from_us(white_to_rg_us);
    ss->rg_settle_ticks = timer_from_us(rg_settle_us);
    ss->xvs_pulse_ticks = timer_from_us(xvs_pulse_us);
    ss->exposure_hold_ticks = timer_from_us(exposure_hold_us);
    ss->rg_to_white_ticks = timer_from_us(rg_to_white_us);
    ss->cycles_remaining = args[1];
    ss->end_white = !!args[9];
    ss->seq = args[10];
    ss->stripe_id = args[11];
    ss->seq_id = args[10];
    ss->frame_id_base = args[12];
    ss->pattern_id = args[13];
    ss->repeat_index = 0;
    ss->emit_af_frame_events = !!args[14];
    ss->safe_output_mask = SS_KNOWN_OUTPUT_MASK;
    ss->safe_output_values = 0;
    ss->idle_output_mask = SS_KNOWN_OUTPUT_MASK;
    ss->idle_output_values = 0;
    ss->state = SS_WHITE_PRE;
    ss->sequence_active = 0;
    ss->running = 1;
    ss->timer_active = 1;
    ss->mcu_time_base = timer_read_time();
    ss->timer.waketime = ss->mcu_time_base + timer_from_us(100);
    sched_add_timer(&ss->timer);
    irq_enable();
}
DECL_COMMAND(command_scanner_sync_af_window_test,
             "scanner_sync_af_window_test oid=%c cycles=%u period_us=%u"
             " white_pre_us=%u white_to_rg_us=%u rg_settle_us=%u"
             " xvs_pulse_us=%u exposure_hold_us=%u rg_to_white_us=%u"
             " end_white=%c seq=%u stripe_id=%u frame_id_base=%i"
             " pattern_id=%u emit_frame_events=%c");

void
command_scanner_sync_af_window_stop(uint32_t *args)
{
    struct scanner_sync *ss = scanner_sync_oid_lookup(args[0]);
    irq_disable();
    scanner_sync_stop_timer(ss);
    ss->sequence_active = 0;
    ss->running = 0;
    scanner_sync_outputs_safe(ss);
    irq_enable();
}
DECL_COMMAND(command_scanner_sync_af_window_stop,
             "scanner_sync_af_window_stop oid=%c");

void
scanner_sync_shutdown(void)
{
    uint8_t oid;
    struct scanner_sync *ss;
    foreach_oid(oid, ss, command_config_scanner_sync_outputs) {
        scanner_sync_stop_timer(ss);
        ss->sequence_active = 0;
        ss->running = 0;
        scanner_sync_outputs_safe(ss);
    }
}
DECL_SHUTDOWN(scanner_sync_shutdown);
