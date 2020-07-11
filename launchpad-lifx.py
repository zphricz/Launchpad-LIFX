#!/usr/bin/env python3

import sys
import queue
import os
import colorsys

from lifxlan import LifxLAN
import launchpad_py as launchpad
import time

NUM_LIGHTS = 3
RATE = 0.1
MIN_WHITE_TEMP = 2500
MAX_WHITE_TEMP = 9000
WHITE_TEMP_DELTA = (MAX_WHITE_TEMP - MIN_WHITE_TEMP) / 10
LOOP_DURATION_SECONDS = 0.1
ERROR_FLASH_DURATION_SECONDS = 3
ERROR_FLASH_FREQUENCY = 6.0
BUTTON_GLOW = 1
BUTTON_RGB = tuple(BUTTON_GLOW for _ in range(3))

lifx = LifxLAN(NUM_LIGHTS)
lights = lifx.get_lights()
i = 0
while len(lights) != 3:
    i += 1
    if i == 10:
        sys.exit(1)
    print("Attempting to open lifx again: {}".format(i))
    time.sleep(10)
    lifx = LifxLAN(NUM_LIGHTS)
    lights = lifx.get_lights()

lp = launchpad.LaunchpadMk2();
if lp.Open( 0, "mk2" ):
    print( " - Launchpad Mk2: OK" )
else:
    print( " - Launchpad Mk2: ERROR" )
    sys.exit(1)
lp.ButtonFlush()

#original_colors = lifx.get_color_all_lights()
#original_powers = lifx.get_power_all_lights()

def detect_lights_on():
    for light, power in lifx.get_power_all_lights().items():
        if power == 0:
            return False
    return True

are_lights_all_on = detect_lights_on()

last_button_glow = None
def set_button_glow(v):
    global last_button_glow
    if v == last_button_glow:
        return
    last_button_glow = v
    lp.LedCtrlXY(0, 0, v, v, v)
    lp.LedCtrlXY(4, 0, v, v, v)
    lp.LedCtrlXY(5, 0, v, v, v)
    lp.LedCtrlXY(8, 1, v, v, v)
    lp.LedCtrlXY(8, 2, v, v, v)
    lp.LedCtrlXY(8, 3, v, v, v)
    lp.LedCtrlXY(8, 4, v, v, v)
    lp.LedCtrlXY(8, 5, v, v, v)
    lp.LedCtrlXY(8, 6, v, v, v)


def shutdown(channel):
    print("Shutting down")
    os.system("sudo shutdown -h now")

def toggle_lights():
    global are_lights_all_on

    if are_lights_all_on:
        lifx.set_power_all_lights("off", rapid=True)
        set_button_glow(1)
    else:
        lifx.set_power_all_lights("on", rapid=True)
        set_button_glow(63)
    are_lights_all_on = not are_lights_all_on

def increment_val(val):
    return min(val + RATE, 1.0)

def decrement_val(val):
    return max(val - RATE, 0.0)


def map_to_base(val, base):
    new_val = int(val * base)
    if new_val == base:
        return new_val - 1
    return new_val

hsvs = {}
rgbs = {}

def build_rgbs_and_hsvs(saturation=1.0, brightness=1.0):
    hue = 0.0
    for x in range(8):
        for y in range(1, 9):
            r, g, b = colorsys.hsv_to_rgb(hue, saturation, brightness)
            rgbs[(x, y)] = (map_to_base(r, 64), map_to_base(g, 64), map_to_base(b, 64))
            hsvs[(x, y)] = (map_to_base(hue, 65536), map_to_base(saturation, 65536), map_to_base(brightness, 65536))
            hue += 1.0 / 64.0

def neighbors(x, y):
    yield (x - 1, y)
    yield (x, y - 1)
    yield (x, y + 1)
    yield (x + 1, y)

def in_bounds(x, y):
    return 0 <= x <= 7 and 1 <= y <= 8

def set_launchpad_wave(mode, wait_ms=15):
    q = queue.Queue()
    last_depth = 0
    q.put(((0, 1), last_depth))
    seen = {(0, 1)}
    while not q.empty():
        ((x, y), depth) = q.get()
        children = [
            (x_neighbor, y_neighbor)
            for (x_neighbor, y_neighbor)
            in neighbors(x, y)
            if (x_neighbor, y_neighbor) not in seen
            and in_bounds(x_neighbor, y_neighbor)
        ]
        for child in children:
            seen.add(child)
            q.put((child, depth + 1))
        if depth != last_depth:
            time.sleep(wait_ms / 1000)
        last_depth = depth
        if mode == "rgb":
            r, g, b = rgbs[(x, y)]
            lp.LedCtrlXY(x, y, r, g, b)
        elif mode == "off":
            lp.LedCtrlXY(x, y, 0, 0, 0)
        else:
            raise Exception("Unknown mode: {}".format(mode))

saturation = 1.0
brightness = 1.0
white_temp = 3800

lp.Reset()
build_rgbs_and_hsvs(saturation=saturation, brightness=brightness)
#set_launchpad_wave(mode="rgb")
#are_launchpad_lights_on = True
are_launchpad_lights_on = False
last_color_xy = None
last_hold_down_button_pressed = None
lifx_is_rgb = False

next_trigger_time = time.time()
try:
    while True:
        #are_lights_all_on = detect_lights_on()
        #if are_lights_all_on:
        #    print("ON")
        #    set_button_glow(max(1, int(round(63 * brightness ** 2))))
        #else:
        #    print("OFF")
        #    set_button_glow(1)
        try:
            next_trigger_time += LOOP_DURATION_SECONDS
            while True:
                buttons_hit = lp.ButtonStateXY()
                if not buttons_hit:
                    # always send some data to prevent buffering issues
                    if are_launchpad_lights_on:
                        r, g, b = rgbs[(0, 1)]
                        lp.LedCtrlXY(0, 1, r, g, b)
                    else:
                        lp.LedCtrlXY(0, 1, 0, 0, 0)
                    break
                x, y, value = buttons_hit
                if value == 0:
                    if (x, y) == last_hold_down_button_pressed:
                        last_hold_down_button_pressed = None
                elif value:
                    if (x, y) == (4, 0):
                        print("toggle lights")
                        toggle_lights()
                        continue
                    elif (x, y) == (5, 0):
                        print("set lights warm")
                        lifx.set_color_all_lights([0, 0, map_to_base(brightness, 65536), white_temp], duration=0, rapid=True)
                        lifx_is_rgb = False
                    elif (x, y) in {(8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6)}:
                        last_hold_down_button_pressed = (x, y)
                    elif (x, y) == (0, 0):
                        if are_launchpad_lights_on:
                            print("launchpad lights off")
                            set_launchpad_wave(mode="off")
                            are_launchpad_lights_on = False
                        else:
                            print("launchpad lights on")
                            set_launchpad_wave(mode="rgb")
                            are_launchpad_lights_on = True
                    if not (x, y) in hsvs:
                        continue
                    h, s, v = hsvs[(x, y)]
                    r, g, b = rgbs[(x, y)]
                    print("(h, s, v) = ({}, {}, {})".format(h, s, b))
                    print("(r, g, b) = ({}, {}, {})".format(r, g, b))
                    lifx.set_color_all_lights([h, s, v, white_temp], duration=0, rapid=True)
                    last_color_xy = (x, y)
                    lifx_is_rgb = True
            if last_hold_down_button_pressed is not None:
                if last_hold_down_button_pressed == (8, 1):
                    saturation = increment_val(saturation)
                    print("increment saturation")
                elif last_hold_down_button_pressed == (8, 2):
                    saturation = decrement_val(saturation)
                    print("decrement saturation")
                elif last_hold_down_button_pressed == (8, 3):
                    brightness = increment_val(brightness)
                    print("increment brightness")
                elif last_hold_down_button_pressed == (8, 4):
                    brightness = decrement_val(brightness)
                    print("decrement brightness")
                elif last_hold_down_button_pressed == (8, 5):
                    white_temp = min(white_temp + WHITE_TEMP_DELTA, MAX_WHITE_TEMP)
                    print("increase color temperature to {}k".format(white_temp))
                elif last_hold_down_button_pressed == (8, 6):
                    white_temp = max(white_temp - WHITE_TEMP_DELTA, MIN_WHITE_TEMP)
                    print("decrease color temperature to {}k".format(white_temp))
                build_rgbs_and_hsvs(saturation=saturation, brightness=brightness)
                if are_launchpad_lights_on:
                    set_launchpad_wave(mode="rgb", wait_ms=0)
                if last_color_xy is not None and lifx_is_rgb:
                    h, s, v = hsvs[last_color_xy]
                    r, g, b = rgbs[last_color_xy]
                    print("(h, s, v) = ({}, {}, {})".format(h, s, b))
                    print("(r, g, b) = ({}, {}, {})".format(r, g, b))
                else:
                    h, s, v = (0, 0, map_to_base(brightness, 65535))
                lifx.set_color_all_lights([h, s, v, white_temp], duration=100, rapid=True)
            current_time = time.time()
            sleep_duration = next_trigger_time - current_time
            if sleep_duration > 0:
                time.sleep(sleep_duration)
        except OSError:
            # This might happen in case of a network disconnect
            err_end_time = time.time() + ERROR_FLASH_DURATION_SECONDS
            hold_duration_seconds = ERROR_FLASH_DURATION_SECONDS / ERROR_FLASH_FREQUENCY / 2
            err_next_trigger_time = time.time() + hold_duration_seconds
            code = lp.LedGetColorByName("red")
            lp.LedAllOn(code)
            on = True
            while time.time() < err_end_time:
                if time.time() >= err_next_trigger_time:
                    if on:
                        lp.LedAllOn(0)
                    else:
                        lp.LedAllOn(code)
                    on = not on
                    err_next_trigger_time += hold_duration_seconds
                time.sleep(.01)
            set_launchpad_wave(mode="rgb")
except KeyboardInterrupt:
    pass
finally:
    lp.Reset()
    lp.Close()

