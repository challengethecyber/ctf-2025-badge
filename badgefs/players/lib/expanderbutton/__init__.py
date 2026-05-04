from machine import Pin, I2C
from time import ticks_ms
import uasyncio as asyncio
from micropython import const

delay = const(5)

class ExpanderButtonException(Exception):
    pass

class ExpanderButton:
    def __init__(
        self,
        bit,
        cb_short=None,
        short_wait=True,
        cb_long=None,
        bounce_time=50,
        long_time=1200,
    ):
        self.bit = bit
        self.cb_short = cb_short or (lambda: None)
        self.short_wait = short_wait
        self.cb_long = cb_long or (lambda: None)
        self.bounce_time = bounce_time
        self.long_time = long_time

        self._time_sh = 0
        self._time_ln = 0
        self._run_sh = False
        self._run_ln = False
        self._pressed = False
        self._last_state = None
        self._trg_delay = False

    def update(self, pressed):
        now = ticks_ms()
        if self._last_state is None:
            self._last_state = pressed
        if pressed != self._last_state:
            if pressed:
                # Button pressed
                self._time_sh = now + self.bounce_time
                self._run_sh = True
                self._time_ln = now + self.long_time
                self._run_ln = True
                self._pressed = True
            else:
                # Button released
                self._pressed = False
                if self._trg_delay:
                    self.cb_short()
                    self._trg_delay = False
                self._run_sh = False
                self._run_ln = False
            self._last_state = pressed

    def check(self):
        now = ticks_ms()
        if self._run_sh:
            if now > self._time_sh:
                self._run_sh = False
                if self._pressed:
                    if self.short_wait:
                        self._trg_delay = True
                    else:
                        self.cb_short()
        if self._run_ln:
            if now > self._time_ln:
                self._run_ln = False
                if self._pressed:
                    self.cb_long()
                    self._trg_delay = False  # Cancel any pending short press


class uButtonExpander:
    def __init__(self, i2c, address, irq_pin, buttons):
        self.i2c = i2c
        self.address = address
        self.irq_pin = irq_pin
        self.buttons = [ExpanderButton(**b) for b in buttons]
        self._changed = True

        # Set up the IRQ
        self.irq_pin.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_handler)

        # Initialize the expander (read initial states)
        self.membank0 = bytearray(1)
        self.membank1 = bytearray(1)

        self.i2c.readfrom_mem_into(self.address, 0, self.membank0)
        self.i2c.readfrom_mem_into(self.address, 1, self.membank1)

    def _irq_handler(self, pin):
        self._changed = True

    async def run(self):
        while True:
            if self._changed:
                # Read the button states
                self.i2c.readfrom_mem_into(self.address, 0, self.membank0)
                self.i2c.readfrom_mem_into(self.address, 1, self.membank1)

                val = self.membank0[0]
                # print("---")
                for btn in self.buttons:
                    bit = btn.bit
                    pressed = not bool(val & (1 << bit))  # Assuming active low buttons
                    # print(pressed)
                    btn.update(pressed)
                self._changed = False

            # For each button, check if timeouts have expired
            for btn in self.buttons:
                btn.check()

            await asyncio.sleep_ms(delay)


class ButtonPress:
    SHORT = 1
    LONG = 2
    ANY_LENGTH = 3

    BUTTON_ENTER = 1
    BUTTON_UP = 2
    BUTTON_DOWN = 3
    ANY_BUTTON = 0

    _press_info = None  # Stores the last button press info as a tuple (button_id, press_type)
    _event = asyncio.Event()  # Asyncio event to signal a button press

    @classmethod
    def handle_press(cls, button_id, press_type):
        cls._press_info = (button_id, press_type)
        cls._event.set()  # Signal that a button has been pressed

    @classmethod
    def reset(cls):
        cls._press_info = None
        cls._event.clear()  # Clear the event so that wait() will block

    @classmethod
    async def wait(cls, length=ANY_LENGTH, button_id=ANY_BUTTON):
        cls.reset()  # Reset the press info and event before waiting
        while True:
            await cls._event.wait()  # Wait for a button press event
            pressed_button_id, pressed_length = cls._press_info

            # Check if the pressed button and length match the desired conditions
            if (button_id == cls.ANY_BUTTON or button_id == pressed_button_id) and (
                length == cls.ANY_LENGTH or length == pressed_length
            ):
                return pressed_button_id, pressed_length
            else:
                # Not the desired button/length, continue waiting
                cls._event.clear()
