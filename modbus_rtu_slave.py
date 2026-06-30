#!/usr/bin/env python3
"""
Modbus RTU slave with 5 auto-oscillating holding registers.

Behaviour
---------
* Spawns a Modbus RTU slave (server) on a serial port.
* Connection settings (port, baudrate, parity, databits, stopbits, unit id)
  and the 5 register start values are asked interactively at startup.
* 5 holding registers (function codes 3 / 6 / 16) that a master can read & write.
* Each register oscillates as a triangle wave between its start value and
  start + 10, stepping by 1 every 5 seconds:  start -> start+10 -> start -> ...
* Master writes are IGNORED: every 5 s the script overwrites all registers
  with its own internal counters.

Requires:  pip install "pymodbus>=3.5,<3.10" pyserial   (see requirements.txt)

Tested against pymodbus 3.6.9.  NOTE: pymodbus 3.11+ removed/deprecated the
classic ModbusSlaveContext API used here, so stay on the pinned range.
"""

import threading

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.server import StartSerialServer

# Framer import path differs slightly across 3.x minors -> be tolerant.
try:
    from pymodbus.framer.rtu_framer import ModbusRtuFramer
except Exception:  # pragma: no cover
    from pymodbus.transaction import ModbusRtuFramer


NUM_REGISTERS = 5
SPAN = 10            # max value = start + SPAN
STEP = 1            # change per tick
INTERVAL = 5.0      # seconds between ticks
HOLDING_FC = 3      # function code that addresses holding registers


# --------------------------------------------------------------------------- #
# Triangle-wave oscillator
# --------------------------------------------------------------------------- #
class Oscillator:
    """Triangle wave between `start` and `start + SPAN`, stepping by STEP."""

    def __init__(self, start):
        self.start = start
        self.max = start + SPAN
        self.value = start
        self.direction = 1  # +1 going up, -1 going down

    def tick(self):
        if self.max == self.start:        # no span -> hold
            return self.value
        self.value += STEP * self.direction
        if self.value >= self.max:
            self.value = self.max
            self.direction = -1
        elif self.value <= self.start:
            self.value = self.start
            self.direction = 1
        return self.value


# --------------------------------------------------------------------------- #
# Context + background updater (transport-independent, so it is unit-testable)
# --------------------------------------------------------------------------- #
def build_context(starts, unit_id):
    """Return (ModbusServerContext, oscillators) seeded with the start values."""
    oscillators = [Oscillator(s) for s in starts]
    block = ModbusSequentialDataBlock(0, [osc.value for osc in oscillators])
    slave = ModbusSlaveContext(hr=block, zero_mode=True)
    context = ModbusServerContext(slaves={unit_id: slave}, single=False)
    return context, oscillators


def updater(context, unit_id, oscillators, stop_event, interval=INTERVAL):
    """Every `interval` s, push current values then advance the oscillators.

    Overwriting the datastore each tick is what makes master writes 'ignored'.
    """
    slave = context[unit_id]
    while not stop_event.is_set():
        values = [osc.value for osc in oscillators]
        slave.setValues(HOLDING_FC, 0, values)
        print("registers:", values, flush=True)

        stop_event.wait(interval)
        if stop_event.is_set():
            break
        for osc in oscillators:
            osc.tick()


# --------------------------------------------------------------------------- #
# Interactive configuration
# --------------------------------------------------------------------------- #
def _ask(prompt, default, cast, valid=None):
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if raw == "":
            return default
        try:
            value = cast(raw)
        except (ValueError, TypeError):
            print("  ! invalid value, try again")
            continue
        if valid is not None and value not in valid:
            print(f"  ! must be one of {sorted(valid)}")
            continue
        return value


def ask_settings():
    print("=== Modbus RTU slave configuration ===")
    cfg = {
        "port": _ask("Serial port", "/dev/ttyUSB0", str),
        "baudrate": _ask("Baudrate", 9600, int),
        "parity": _ask("Parity (N/E/O)", "N", lambda s: s.upper(), valid={"N", "E", "O"}),
        "bytesize": _ask("Data bits (7/8)", 8, int, valid={7, 8}),
        "stopbits": _ask("Stop bits (1/2)", 1, int, valid={1, 2}),
        "unit_id": _ask("Slave / unit id", 1, int),
    }
    print("\n--- Start values for the 5 registers ---")
    cfg["starts"] = [
        _ask(f"Register {i} start value", 1, int) for i in range(NUM_REGISTERS)
    ]
    return cfg


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    cfg = ask_settings()
    context, oscillators = build_context(cfg["starts"], cfg["unit_id"])

    stop_event = threading.Event()
    t = threading.Thread(
        target=updater,
        args=(context, cfg["unit_id"], oscillators, stop_event),
        daemon=True,
    )
    t.start()

    print(
        f"\nStarting RTU slave on {cfg['port']} "
        f"@ {cfg['baudrate']} {cfg['bytesize']}{cfg['parity']}{cfg['stopbits']}, "
        f"unit id {cfg['unit_id']}.  Ctrl+C to stop.\n"
    )
    try:
        StartSerialServer(
            context=context,
            framer=ModbusRtuFramer,
            port=cfg["port"],
            baudrate=cfg["baudrate"],
            parity=cfg["parity"],
            bytesize=cfg["bytesize"],
            stopbits=cfg["stopbits"],
            timeout=1,
        )
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stop_event.set()
        t.join(timeout=2)


if __name__ == "__main__":
    main()
