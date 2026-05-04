import asyncio
import micropython

import expanderbutton
from .utils import print_output

DEBUG = micropython.const(False)


class BaseApp:
    def __init__(self, eink, max_index, uart=None, neopixels=None):
        self._eink = eink
        self._uart = uart
        self._neopixels = neopixels

        self._current_index = 0
        self._max_index = max_index
        self._circular_index = True

        self._stopped = False
        self._draw_event = asyncio.Event()
        self._draw_event.set()

        self._first_draw = True

    async def _draw_task(self):
        while True:
            await self._draw_event.wait()
            self._draw_event.clear()

            if self._stopped:
                break

            await self._draw()

    async def _buttons_task(self):
        while True:
            button_id, press_type = await expanderbutton.ButtonPress.wait(
                expanderbutton.ButtonPress.ANY_LENGTH, expanderbutton.ButtonPress.ANY_BUTTON
            )

            if press_type == expanderbutton.ButtonPress.SHORT and button_id == expanderbutton.ButtonPress.BUTTON_UP:
                if not self._circular_index:
                    self._current_index = self._current_index - 1
                else:
                    self._current_index = self._current_index - 1 if self._current_index > 0 else self._max_index
                if DEBUG:
                    print_output(__name__, f"index: {self._current_index}")
                self._draw_event.set()
            elif press_type == expanderbutton.ButtonPress.SHORT and button_id == expanderbutton.ButtonPress.BUTTON_DOWN:
                if not self._circular_index:
                    self._current_index = self._current_index + 1
                else:
                    self._current_index = self._current_index + 1 if self._current_index < self._max_index else 0
                if DEBUG:
                    print_output(__name__, f"index: {self._current_index}")

                self._draw_event.set()

            if press_type == expanderbutton.ButtonPress.LONG and button_id == expanderbutton.ButtonPress.BUTTON_ENTER:
                if DEBUG:
                    print_output(__name__, f"stopping")

                self._stopped = True
                self._draw_event.set()
                return

    async def _draw(self):
        # We want the nametag to be displayed clearly without ghosting.
        if self._first_draw:
            await self._eink.display(partial_update=False)
            self._first_draw = False
        else:
            await self._eink.display()

    async def main(self):
        loop = asyncio.get_event_loop()
        _ = await asyncio.gather(loop.create_task(self._draw_task()), loop.create_task(self._buttons_task()))
