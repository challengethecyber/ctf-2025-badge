import asyncio
import machine
import micropython
import ucollections

import expanderbutton
import textwriter

from .nametag import app_nametag
from .game import app_game
from .rolodex import app_rolodex
from .utils import get_darkmode, load_fonts, print_output, set_darkmode, make_image, get_team_id

DEBUG = micropython.const(False)

class Menu:
    def __init__(self, eink, uart):
        self._eink = eink
        self._uart = uart

        self._fonts = load_fonts("hack")
        self._fonts_bold = load_fonts("hackbold")
        self._item_font = self._fonts_bold[18]
        self._btid_font = self._fonts[12]
        self._textwriter = textwriter.TextWriter(self._eink, self._fonts, self._fonts_bold)
        # self._first_boot = True

        self._entries = ucollections.OrderedDict(
            [
                ("Nametag", {"app": app_nametag}),
                ("ChoHanGame", {"app": app_game}),
                ("Rolodex", {"app": app_rolodex}),
                ("DarkMode" if not get_darkmode() else "LightMode", {"function": Menu._switch_mode_reboot}),
            ]
        )

        self._current_index = 0
        self._max_index = len(self._entries) - 1
        
    @classmethod
    def _switch_mode_reboot(cls):
        set_darkmode(not get_darkmode())
        machine.reset()

    async def _update_current_indicator(self, starting_y):
        self._eink.fb.rect(5, starting_y, 15, self._item_font.height * (len(self._entries) + 1), 0, True)
        self._textwriter.write_text(
            f">", self._item_font, 7, starting_y + self._item_font.height * (self._current_index)
        )

    async def _init_menu(self):
        self._eink.fb.fill(0)
        self._eink.fb.blit(make_image("ctc2025", 126, 18), 13, 10)
        self._textwriter.write_text("{:>6}".format(get_team_id(True,True)), self._btid_font, 107, 137)

        starting_y = 35

        current_y = starting_y
        for _, (name, _) in enumerate(self._entries.items()):
            self._textwriter.write_text(f"  {name}", self._item_font, 7, current_y)
            current_y += self._item_font.height

        return starting_y

    async def _update_screen_task(self, update_screen_event, starting_y):
        while True:
            await update_screen_event.wait()
            update_screen_event.clear()

            await self._update_current_indicator(starting_y)
            await self._eink.display()

    async def _process_buttons_task(self, update_screen_event):
        while True:
            button_id, press_type = await expanderbutton.ButtonPress.wait(
                expanderbutton.ButtonPress.ANY_LENGTH, expanderbutton.ButtonPress.ANY_BUTTON
            )

            if press_type == expanderbutton.ButtonPress.SHORT and button_id == expanderbutton.ButtonPress.BUTTON_UP:
                self._current_index = self._current_index - 1 if self._current_index > 0 else self._max_index

                if DEBUG:
                    print_output(__name__, f"Index: {self._current_index}")

                update_screen_event.set()
            elif press_type == expanderbutton.ButtonPress.SHORT and button_id == expanderbutton.ButtonPress.BUTTON_DOWN:
                self._current_index = self._current_index + 1 if self._current_index < self._max_index else 0

                if DEBUG:
                    print_output(__name__, f"Index: {self._current_index}")

                update_screen_event.set()
            elif (
                press_type == expanderbutton.ButtonPress.SHORT and button_id == expanderbutton.ButtonPress.BUTTON_ENTER
            ):
                (_, item) = list(self._entries.items())[self._current_index]

                if item is not None:
                    if "app" in item:
                        # Start app.
                        await item["app"](self._eink, uart=self._uart)

                        # App is finished.
                        _ = await self._init_menu()
                        update_screen_event.set()
                    if "function" in item:
                        item["function"]()

    async def main(self):
        starting_y = await self._init_menu()
        update_screen_event = asyncio.Event()
        update_screen_event.set()

        loop = asyncio.get_event_loop()
        update_screen_task = loop.create_task(self._update_screen_task(update_screen_event, starting_y))
        process_buttons_task = loop.create_task(self._process_buttons_task(update_screen_event))
        _ = await asyncio.gather(update_screen_task, process_buttons_task)


async def task_menu(boot_promise, eink, uart):
    await boot_promise
    await Menu(eink, uart).main()
