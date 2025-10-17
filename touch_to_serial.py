#!/usr/bin/env python3
"""
touch_to_serial_with_preview.py

Reads touchscreen events (evdev), maps to target (IPHONE_W,IPHONE_H),
and sends text messages "DOWN x y", "MOVE x y", "UP x y" over serial.

If the configured SERIAL_PORT is not available, the script:
 - prints every outgoing line to stdout, and
 - opens a PTY pair and writes the same lines to the PTY master so you can monitor the slave device.

Requirements:
  sudo apt install python3-pip
  pip3 install evdev pyserial

Run:
  sudo python3 touch_to_serial_with_preview.py
"""

import os
import sys
import time
import argparse
import errno
import pty
import os
from evdev import InputDevice, list_devices, ecodes

try:
    import serial
except Exception:
    serial = None

# ---------- CONFIG (defaults; can pass via args) ----------
DEFAULT_SERIAL = "/dev/ttyUSB0"
DEFAULT_BAUD = 115200
SCREEN_W = 800   # change to your touchscreen pixel width
SCREEN_H = 480   # change to your touchscreen pixel height
IPHONE_W = 828   # logical iPhone width (or choose arbitrary mapping)
IPHONE_H = 1792  # logical iPhone height
# ---------------------------------------------------------

def find_touch_device():
    devices = [InputDevice(path) for path in list_devices()]
    # heuristics: name contains 'touch' or capabilities include ABS_X/ABS_Y
    for d in devices:
        name = d.name.lower()
        if "touch" in name or "touchscreen" in name or "goodix" in name or "ft" in name:
            print(f"[touch] chosen by name: {d.path} -> {d.name}")
            return d
    # fallback: find device with ABS_X/ABS_Y or ABS_MT_POSITION_X/Y
    for d in devices:
        caps = d.capabilities()
        if any(code in caps for code in (ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_MT_POSITION_X, ecodes.ABS_MT_POSITION_Y)):
            print(f"[touch] chosen by capability: {d.path} -> {d.name}")
            return d
    print("[touch] no touchscreen input device found. Devices discovered:")
    for d in devices:
        print("  ", d.path, "-", d.name)
    raise FileNotFoundError("No touchscreen device found. Check `ls /dev/input` and run this as root or add udev rules.")

def open_serial_or_pty(serial_port, baud):
    """
    Try to open a real serial.Serial; if fail, return (None, pty_slave_path, master_fd)
    If success, return (serial_obj, None, None)
    """
    if serial is None:
        print("[serial] pyserial not available; falling back to PTY/print.")
        return None, create_pty_and_report()
    try:
        s = serial.Serial(serial_port, baud, timeout=0)
        print(f"[serial] opened {serial_port} @ {baud}")
        return s, None, None
    except Exception as e:
        print(f"[serial] failed to open {serial_port}: {e}. Falling back to PTY + stdout preview.")
        return None, create_pty_and_report()

def create_pty_and_report():
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)
    print(f"[pty] created PTY. You can monitor output with: cat {slave_name}  (or use screen/minicom on the slave).")
    # We'll write to master_fd.
    return (slave_name, master_fd)

def map_coords(sx, sy, screen_w, screen_h, iphone_w, iphone_h):
    # simple linear map (assumes mirrored video is full-screen and non-cropped)
    tx = int(sx * (iphone_w / screen_w))
    ty = int(sy * (iphone_h / screen_h))
    return tx, ty

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", "-s", default=DEFAULT_SERIAL, help="Serial port for ESP32 (e.g. /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=DEFAULT_BAUD, help="Serial baud rate")
    parser.add_argument("--screen-w", type=int, default=SCREEN_W)
    parser.add_argument("--screen-h", type=int, default=SCREEN_H)
    parser.add_argument("--iphone-w", type=int, default=IPHONE_W)
    parser.add_argument("--iphone-h", type=int, default=IPHONE_H)
    args = parser.parse_args()

    try:
        dev = find_touch_device()
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    serial_obj, pty_info, master_fd = None, None, None
    # open serial or fallback
    result = open_serial_or_pty(args.serial, args.baud)
    if isinstance(result[0], object) and result[0] is not None:
        serial_obj = result[0]
    else:
        # fallback: result == (None, (slave_name, master_fd))
        pty_info = result[1]
        # pty_info is a tuple (slave_name, master_fd) returned by create_pty_and_report()
        if isinstance(pty_info, tuple):
            slave_name, master_fd = pty_info
        else:
            # compatibility: create_pty_and_report previously returned (slave_name, master_fd)
            slave_name, master_fd = pty_info

    print(f"[info] using touch device {dev.path} ({dev.name})")
    print(f"[info] mapping screen {args.screen_w}x{args.screen_h} -> iPhone {args.iphone_w}x{args.iphone_h}")
    print("[info] starting event loop. Ctrl-C to quit.")

    # state
    touching = False
    cur_sx = cur_sy = 0
    last_tx = last_ty = None

    try:
        for ev in dev.read_loop():
            # ABS events give coordinates
            if ev.type == ecodes.EV_ABS:
                code = ev.code
                if code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_X):
                    cur_sx = ev.value
                elif code in (ecodes.ABS_MT_POSITION_Y, ecodes.ABS_Y):
                    cur_sy = ev.value

                # if we already have an active touch, emit MOVE
                if touching:
                    tx, ty = map_coords(cur_sx, cur_sy, args.screen_w, args.screen_h, args.iphone_w, args.iphone_h)
                    if tx != last_tx or ty != last_ty:
                        line = f"MOVE {tx} {ty}\n"
                        # write to serial or PTY/master and print
                        if serial_obj:
                            try:
                                serial_obj.write(line.encode('ascii'))
                            except Exception as e:
                                print("[serial] write failed:", e)
                                serial_obj = None
                        else:
                            # write to PTY master to simulate serial device
                            try:
                                os.write(master_fd, line.encode('ascii'))
                            except Exception as e:
                                # sometimes the other side isn't reading; ignore
                                pass
                        # always print to stdout for debug
                        print("[OUT]", line.strip())
                        last_tx, last_ty = tx, ty

            # KEY events: BTN_TOUCH indicates press/release on many touch drivers
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                val = ev.value
                tx, ty = map_coords(cur_sx, cur_sy, args.screen_w, args.screen_h, args.iphone_w, args.iphone_h)
                if val == 1 and not touching:
                    touching = True
                    last_tx, last_ty = tx, ty
                    line = f"DOWN {tx} {ty}\n"
                elif val == 0 and touching:
                    touching = False
                    line = f"UP {tx} {ty}\n"
                    last_tx = last_ty = None
                else:
                    line = None

                if line:
                    if serial_obj:
                        try:
                            serial_obj.write(line.encode('ascii'))
                        except Exception as e:
                            print("[serial] write failed:", e)
                            serial_obj = None
                    else:
                        try:
                            os.write(master_fd, line.encode('ascii'))
                        except Exception:
                            pass
                    print("[OUT]", line.strip())
            # optional: map BTN_TOOL_* or SYN events if needed
    except KeyboardInterrupt:
        print("\n[info] exiting")
    finally:
        if serial_obj:
            try:
                serial_obj.close()
            except:
                pass
        if master_fd:
            try:
                os.close(master_fd)
            except:
                pass

if __name__ == "__main__":
    main()
