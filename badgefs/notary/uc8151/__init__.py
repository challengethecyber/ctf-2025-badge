# Frankensteined driver for GDEW0154M10 / @c3c based on GxEPD2.
# MicroPython driver for the UC8151 / IL0373 e-paper display.
# Some elements from Salvatore Sanfilippo's uc8151_micropython lib.

import asyncio
import time

import machine

import customframebuf

from .cmd import *
from .const import *

BENCHMARK = micropython.const(False)
DEBUG = micropython.const(False)


def benchmark_start():
    return time.ticks_ms()


def benchmark_print(name, value, time_start):
    print_output(name, f"{value}: {time.ticks_ms() - time_start}ms")


def print_output(name, value):
    print(f"[{time.ticks_ms()}] {name}: {value}")


class UC8151:
    def __init__(self, spi, cs, dc, rst, busy, darkmode=False):
        self._spi = spi
        self._cs_pin = machine.Pin(cs, machine.Pin.OUT)
        self._dc_pin = machine.Pin(dc, machine.Pin.OUT)
        self._rst_pin = machine.Pin(rst, machine.Pin.OUT)
        self._busy_pin = machine.Pin(busy, machine.Pin.IN)

        self._darkmode = darkmode

        self._width = 152
        self._height = 152

        self._buffer = bytearray(self._width * self._height // 8)
        self._fb = customframebuf.CustomFrameBuffer(self._buffer, self._width, self._height)
        self._rotated_buffer = bytearray(self._width * self._height // 8)

        # Track if a refresh is the first refresh or not.
        self._first_refresh = True

        self._power_is_on = False
        self._using_partial_mode = False

        # Counts the amount of partial updates that have occured.
        self._partial_update_counter = 0
        # Limit the number of consecutive partial updates to prevent burn-in.
        self._max_partial_updates = 500

        self._hardware_reset()

    # Expose the framebuffer as a property.
    @property
    def fb(self):
        return self._fb

    # Expose the buffer as a property.
    @property
    def buffer(self):
        return self._buffer

    # Expose the width of the display as a property.
    @property
    def width(self):
        return self._width

    # Expose the height of the display as a property.
    @property
    def height(self):
        return self._height

    async def display(self, partial_update=True):
        """Updates the display with the latest framebuffer content.

        Args:
            partial_update (bool, optional): Perform a partial update of the screen (faster). Defaults to True.
        """
        if partial_update:
            # Track the number of consecutive partial updates.
            self._partial_update_counter += 1

            # If the maximum number of partial updates has been exceeded, force
            # a full update, and reset the counter.
            if self._partial_update_counter > self._max_partial_updates:
                partial_update = False
                self._partial_update_counter = 0

                if DEBUG:
                    print_output(__name__, f"Forcing full refresh")
        else:
            # If a full update occurs, reset the partial update counter.
            self._partial_update_counter = 0

        await self._write_fb()
        await self._refresh(partial_update)

        # TODO: Left out, seems to work, is this ok?
        # await self._write_fb()

        # Power off the screen if a non-partial update has occured.
        if not partial_update:
            await self._power_off()

    async def wait_ready(self):
        if BENCHMARK:
            _benchmark = benchmark_start()

        # Waits until the display is not busy updating anymore.
        while self._is_busy:
            await asyncio.sleep_ms(25)

        if BENCHMARK:
            benchmark_print(__name__, "wait_ready", _benchmark)

    async def _update(self):
        await self._write_spi(CMD_DRF)
        while self._is_busy:
            await asyncio.sleep_ms(25)

    async def _refresh(self, partial_update_mode):
        if BENCHMARK:
            _benchmark = benchmark_start()

        if partial_update_mode:
            await self._refresh_coords()
        else:
            if self._using_partial_mode:
                await self._init_full()

            await self._update()
            self._first_refresh = False

        if BENCHMARK:
            benchmark_print(__name__, "_refresh", _benchmark)

    async def _refresh_coords(self):
        if BENCHMARK:
            _benchmark = benchmark_start()

        if self._first_refresh:
            return await self._refresh(False)

        if not self._using_partial_mode:
            await self._init_part()

        self._write_spi(CMD_PTIN)
        self._set_partial_ramarea()
        await self._update()
        self._write_spi(CMD_PTOU)

        if BENCHMARK:
            benchmark_print(__name__, "_refresh_coords", _benchmark)

    async def _set_partial_ramarea(self):
        await self._write_spi(CMD_PTL, [0, 151, 0, 0, 0, 151, 1])

    async def _init_display(self):
        if BENCHMARK:
            _benchmark = benchmark_start()

        await self._write_spi(CMD_PSR, BOOSTER_ON | RESET_NONE | SCAN_DOWN | SHIFT_RIGHT | FORMAT_BW | LUT_OTP)
        await self._write_spi(CMD_CDI, 0b01_01_01_11 if self._darkmode else 0b01_00_01_11)
        await self._write_spi(CMD_TRES, [152, 0, 152])

        if BENCHMARK:
            benchmark_print(__name__, "_init_display", _benchmark)

    async def _init_part(self):
        if DEBUG:
            print_output(__name__, f"Switching to partial update mode")

        if BENCHMARK:
            _benchmark = benchmark_start()

        await self._init_display()

        await self._write_spi(
            CMD_PSR, BOOSTER_ON | RESET_NONE | SCAN_DOWN | SHIFT_RIGHT | FORMAT_BW | LUT_REG
        )  # LUT from REG

        await self._write_spi(
            CMD_PWR, [VDS_INTERNAL | VDG_INTERNAL, VCOM_VD | VGHL_16V, 0b100110, 0b100110, 0b000011]
        )  # Power setting
        await self._write_spi(CMD_VDCS, 0x12)

        await self._write_spi(CMD_CDI, 0b00_01_01_11 if self._darkmode else 0b00_00_01_11)
        await self._write_luts()

        await self._write_spi(
            CMD_BTST,
            [
                START_10MS | STRENGTH_3 | OFF_6_58US,
                START_10MS | STRENGTH_3 | OFF_6_58US,
                START_10MS | STRENGTH_3 | OFF_6_58US,
            ],
        )

        await self._write_spi(CMD_PFS, FRAMES_4)
        await self._write_spi(CMD_TSE, TEMP_INTERNAL | OFFSET_0)
        await self._write_spi(CMD_TCON, 0x22)
        await self._write_spi(CMD_PLL, HZ_100)

        await self._power_on()
        self._using_partial_mode = True

        if BENCHMARK:
            benchmark_print(__name__, "_init_part", _benchmark)

    async def _write_luts(self):
        period = 20 if self._darkmode else 10
        lut_vcom = [0x00, period, 0, period * 7, 0, 1]
        lut_ww = [0b00_00_00_00, period, 0, period * 7, 0, 1]
        lut_bw = [0b01_01_10_10, period, 0, period * 7, 0, 1]
        lut_wb = [0b10_10_01_01, period, 0, period * 7, 0, 1]
        lut_bb = [0b00_00_00_00, period, 0, period * 7, 0, 1]

        await self._write_spi(CMD_LUT_VCOM, bytes(lut_vcom) + b"\x00" * 30)
        await self._write_spi(CMD_LUT_WW, bytes(lut_ww) + b"\x00" * 30)
        await self._write_spi(CMD_LUT_BW, bytes(lut_bw) + b"\x00" * 30)
        await self._write_spi(CMD_LUT_WB, bytes(lut_wb) + b"\x00" * 30)
        await self._write_spi(CMD_LUT_BB, bytes(lut_bb) + b"\x00" * 30)

    async def _init_full(self):
        if DEBUG:
            print_output(__name__, f"Switching to full update mode")

        if BENCHMARK:
            _benchmark = benchmark_start()

        await self._init_display()
        await self._power_on()
        self._using_partial_mode = False

        if BENCHMARK:
            benchmark_print(__name__, "_init_full", _benchmark)

    async def _power_on(self):
        await self._write_spi(CMD_PON)
        while self._is_busy:
            await asyncio.sleep_ms(25)

        self._power_is_on = True

    async def _power_off(self):
        if self._power_is_on:
            await self._write_spi(CMD_POF)
            while self._is_busy:
                await asyncio.sleep_ms(25)

        self._power_is_on = False
        self._using_partial_mode = False

    async def _write_fb(self):
        _benchmark = benchmark_start()

        if not self._using_partial_mode:
            await self._init_part()

        await self._write_spi(CMD_PTIN)
        await self._set_partial_ramarea()

        _benchmark_rotation = benchmark_start()

        self._fb.rotate(self._rotated_buffer)

        if BENCHMARK:
            benchmark_print(__name__, "_write_fb rotation", _benchmark_rotation)

        await self._write_spi(CMD_DTM2, self._rotated_buffer)
        await self._write_spi(CMD_PTOU)

        if BENCHMARK:
            benchmark_print(__name__, "_write_fb", _benchmark)

    # Return true if the display is busy performing an update, or also
    # if for any other reason it is not able to accept commands right now.
    @property
    def _is_busy(self):
        return self._busy_pin.value() == False  # Low on busy condition.

    # Perform hardware reset, perform timings synchronously.
    def _hardware_reset(self):
        self._rst_pin.off()
        time.sleep_ms(10)
        self._rst_pin.on()
        time.sleep_ms(10)

    def _set_dc_command_mode(self):
        self._dc_pin.off()  # Command mode

    def _set_dc_data_mode(self):
        self._dc_pin.on()  # Data mode

    async def _write_spi(self, cmd=None, data=None):
        await self.wait_ready()

        self._cs_pin.off()

        if cmd is not None:
            self._set_dc_command_mode()
            self._spi.write(bytes([cmd]))

        if data is not None:
            if isinstance(data, int):
                data = bytes([data])
            if isinstance(data, list):
                data = bytes(data)

            self._set_dc_data_mode()
            self._spi.write(data)

        self._cs_pin.on()
