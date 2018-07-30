#!/usr/bin/env python3
# coding=utf-8
import sys
from time import sleep
import queue
import time
import os
import RPi.GPIO as GPIO
import colorsys

from lifxlan import LifxLAN
import launchpad_py as launchpad
from pygame import time

WARM_COLOR = [0, 0, 65535, 3500]
NUM_LIGHTS = 3

lifx = LifxLAN(NUM_LIGHTS)
lights = lifx.get_lights()
i = 0
while len(lights) != 3:
    i += 1
    if i == 10:
        sys.exit(1)
    print("Attempting to open lifx again: i")
    sleep(10)
    lifx = LifxLAN(NUM_LIGHTS)
    lights = lifx.get_lights()

lp = launchpad.LaunchpadMk2();
if lp.Open( 0, "mk2" ):
    print( " - Launchpad Mk2: OK" )
else:
    print( " - Launchpad Mk2: ERROR" )
    sys.exit(1)
lp.ButtonFlush()


original_colors = lifx.get_color_all_lights()
original_powers = lifx.get_power_all_lights()

are_lights_all_on = True
for light, power in lifx.get_power_all_lights().items():
    if power == 0:
        are_lights_all_on = False

def shutdown(channel):
    print("Shutting down")
    os.system("sudo shutdown -h now")

def toggle_lights():
    global are_lights_all_on

    if are_lights_all_on:
        lifx.set_power_all_lights("off", rapid=True)
    else:
        lifx.set_power_all_lights("on", rapid=True)
        #lifx.set_color_all_lights(WARM_COLOR, duration=1000, rapid=True)
    are_lights_all_on = not are_lights_all_on

class RGB(object):
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b

    def to_tuple(self):
        return self.r, self.g, self.b

#hues = [[None] * 10] * 10
#rgbs = [[None] * 10] * 10
hues = {}
rgbs = {}

hue = 0
for x in range(8):
    for y in range(1, 9):
        r, g, b = colorsys.hsv_to_rgb(hue / 65535, 1.0, 1.0)
        rgb = RGB(int(64 * r), int(64 * g), int(64 * b))
        rgbs[(x, y)] = rgb
        hues[(x, y)] = int(hue)
        hue += 65535 / 64

def neighbors(x, y):
    #yield (x - 1, y - 1)
    yield (x - 1, y)
    #yield (x - 1, y + 1)
    yield (x, y - 1)
    yield (x, y + 1)
    #yield (x + 1, y - 1)
    yield (x + 1, y)
    #yield (x + 1, y + 1)

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
            time.wait(wait_ms)
        last_depth = depth
        if mode == "rgb":
            r, g, b = rgbs[(x, y)].to_tuple()
            lp.LedCtrlXY(x, y, r, g, b)
        elif mode == "off":
            lp.LedCtrlXY(x, y, 0, 0, 0)
        else:
            raise Exception("Unknown mode: {}".format(mode))
    #for x in range(8):
    #    for y in range(1, 9):
    #        r, g, b = rgbs[(x, y)].to_tuple()
    #        lp.LedCtrlXY(x, y, r, g, b)

lp.Reset()
#lp.LedCtrlXY(0, 1, r, g, b)
set_launchpad_wave(mode="rgb")
is_rgb = True

try:
    while True:
        while True:
            buttons_hit = lp.ButtonStateXY()
            if not buttons_hit:
                # send some data to prevent buffering issues
                if is_rgb:
                    r, g, b = rgbs[(0, 1)].to_tuple()
                    lp.LedCtrlXY(0, 1, r, g, b)
                else:
                    lp.LedCtrlXY(0, 1, 0, 0, 0)
                break
            x, y, value = buttons_hit
            if value:
                if (x, y) == (4, 0):
                    #shutdown()
                    print("toggle")
                    toggle_lights()
                    continue
                elif (x, y) == (5, 0):
                    print("warm")
                    lifx.set_color_all_lights(WARM_COLOR, duration=0, rapid=True)
                elif (x, y) == (0, 0):
                    if is_rgb:
                        set_launchpad_wave(mode="off")
                        #lp.Reset()
                        is_rgb = False
                    else:
                        set_launchpad_wave(mode="rgb")
                        is_rgb = True
                if not (x, y) in hues:
                    continue
                hue = hues[(x, y)]
                #hue = hues[x][y]
                print(hue)
                lifx.set_color_all_lights([hue, 65535, 65535, 0], duration=0, rapid=True)
        time.wait(100)
except KeyboardInterrupt:
    lp.Reset()
    lp.Close()

