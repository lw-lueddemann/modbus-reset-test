# Modbus RTU Slave — auto-oscillating registers

A small bench/test tool that spawns a **Modbus RTU slave (server)** on a serial
port, exposing **5 holding registers** that a master can read and write. Each
register moves on its own over time so you can watch live values change.

## What it does

- Asks at startup for the connection settings and the 5 register start values.
- Serves **5 holding registers** (function codes 3 / 6 / 16 — readable & writable).
- Each register oscillates as a **triangle wave** between its start value and
  `start + 10`, stepping by **1 every 5 seconds**: `start → start+10 → start → …`
  forever.
  - e.g. start `10` → `11, 12, … 20, 19, … 10, 11, …`
- **Master writes are ignored**: every 5 s the script overwrites all registers
  with its own internal counters.
- Prints the current register values to the console each tick.

## Requirements

- **Python 3.9+**
- **pymodbus** in the `3.5–3.9` range (pinned in `requirements.txt`, verified on
  `3.6.9`).
  > ⚠️ Do **not** just `pip install pymodbus`. pymodbus 3.11+ removed the classic
  > API this script uses — always install from `requirements.txt`.
- **pyserial**
- A serial port to bind to: a real USB-serial adapter (`/dev/ttyUSB0`,
  `/dev/tty.usbserial-XXXX`, `COM3`, …) or a virtual one (e.g. `socat`).

## Install

Using a virtual environment (recommended):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Or install globally:

```bash
pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python modbus_rtu_slave.py
```

You'll be prompted for (press Enter to accept the `[default]`):

| Prompt              | Default        | Notes                          |
|---------------------|----------------|--------------------------------|
| Serial port         | `/dev/ttyUSB0` | e.g. `/dev/tty.usbserial-A50285BI`, `COM3` |
| Baudrate            | `9600`         |                                |
| Parity (N/E/O)      | `N`            | None / Even / Odd              |
| Data bits (7/8)     | `8`            |                                |
| Stop bits (1/2)     | `1`            |                                |
| Slave / unit id     | `1`            | Modbus unit the slave answers as |
| Register 0–4 start  | `1`            | Start value per register       |

Then it starts serving and prints each tick:

```
registers: [1, 5, 10, 15, 20]
registers: [2, 6, 11, 16, 21]
...
```

Press **Ctrl+C** to stop.

## Testing without hardware

If you don't have a serial adapter, create a virtual serial pair with `socat`
(`brew install socat` on macOS):

```bash
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

It prints two `/dev/ttysNNN` paths. Point the slave at one and your Modbus
master at the other.

## Notes

- The slave addresses registers from **0** (zero-based), so a master reads
  holding registers at addresses `0..4`.
- The oscillation parameters (`SPAN = 10`, `STEP = 1`, `INTERVAL = 5.0`) are
  constants near the top of `modbus_rtu_slave.py` if you want to change them.
