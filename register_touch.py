from evdev import InputDevice, categorize, ecodes

# Replace with your actual device number
dev = InputDevice('/dev/input/event0')

print(dev)  # See device info
print("Listening for touches...")

for event in dev.read_loop():
    if event.type == ecodes.EV_ABS:
        if event.code == ecodes.ABS_MT_POSITION_X:
            x = event.value
        elif event.code == ecodes.ABS_MT_POSITION_Y:
            y = event.value
        try:
            print(f"Touch at ({x}, {y})")
        except NameError:
            pass
