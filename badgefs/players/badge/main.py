import gc
gc.enable()

import micropython
micropython.alloc_emergency_exception_buf(100)

import asyncio
import machine
import neopixel
import ntptime
import sys
import expanderbutton
import textwriter
import uc8151

from .utils import get_team_id, get_darkmode, load_fonts, make_image, print_output

# Apps
from .nametag import Nametag

# Tasks
from .menu import task_menu
from .rolodex import task_serial_send

BENCHMARK = micropython.const(True)
DEBUG = micropython.const(False)

BUTTON_EXPANDER_I2C_ADDRESS = micropython.const(0x26)
BUTTON_EXPANDER_PIN = micropython.const(2)

EINK_CS_PIN = micropython.const(5)
EINK_DC_PIN = micropython.const(4)
EINK_RST_PIN = micropython.const(10)
EINK_BUSY_PIN = micropython.const(3)
EINK_SCK_PIN = micropython.const(6)
EINK_MOSI_PIN = micropython.const(7)
EINK_SPEED = micropython.const(4)

I2C_SDA_PIN = micropython.const(20)
I2C_SCL_PIN = micropython.const(21)

NEOPIXELS_PIN = micropython.const(8)

SERIAL_TX_PIN = micropython.const(0)
SERIAL_RX_PIN = micropython.const(1)

_fonts_regular = load_fonts("hack")
_fonts_bold = load_fonts("hackbold")

async def _async_exception_handler(eink, exception):
    eink.fb.fill(0)

    text_writer = textwriter.TextWriter(eink, _fonts_regular, _fonts_bold)
    current_y = 0

    smiley_font = _fonts_bold[36]
    text_font = _fonts_regular[16]

    text_writer.write_text_center(":(", smiley_font, current_y)
    current_y += smiley_font.height + 10

    text_font = _fonts_regular[16]
    text_writer.write_text("Your badge ran", text_font, 0, current_y)
    current_y += text_font.height
    text_writer.write_text("into a problem", text_font, 0, current_y)
    current_y += text_font.height
    text_writer.write_text("and needs to", text_font, 0, current_y)
    current_y += text_font.height
    text_writer.write_text("restart.", text_font, 0, current_y)
    current_y += text_font.height*2
    
    if isinstance(exception, expanderbutton.ExpanderButtonException):
        text_font = _fonts_regular[14]
        text_writer.write_text("Try another USB port.", text_font, 0, current_y)
        current_y += text_font.height

    await eink.display()
    await asyncio.sleep(2)

    machine.reset()


def _exception_handler(_, context):
    sys.print_exception(context["exception"])

    eink = _setup_eink_screen()
    new_loop = asyncio.new_event_loop()
    new_loop.run_until_complete(_async_exception_handler(eink=eink, exception=context["exception"]))
    

def _setup_eink_screen():
    return uc8151.UC8151(
        spi=machine.SPI(
            1,
            baudrate=20000000,
            phase=0,
            polarity=0,
            sck=EINK_SCK_PIN,
            mosi=EINK_MOSI_PIN,
        ),
        cs=EINK_CS_PIN,
        dc=EINK_DC_PIN,
        rst=EINK_RST_PIN,
        busy=EINK_BUSY_PIN,
        darkmode=get_darkmode(),
    )


def _setup_button_expander():
    buttons = [
        {
            "bit": 3,
            "cb_short": lambda: expanderbutton.ButtonPress.handle_press(
                expanderbutton.ButtonPress.BUTTON_ENTER, expanderbutton.ButtonPress.SHORT
            ),
            "cb_long": lambda: expanderbutton.ButtonPress.handle_press(
                expanderbutton.ButtonPress.BUTTON_ENTER, expanderbutton.ButtonPress.LONG
            ),
        },
        {
            "bit": 4,
            "cb_short": lambda: expanderbutton.ButtonPress.handle_press(
                expanderbutton.ButtonPress.BUTTON_UP, expanderbutton.ButtonPress.SHORT
            ),
            "cb_long": lambda: expanderbutton.ButtonPress.handle_press(
                expanderbutton.ButtonPress.BUTTON_UP, expanderbutton.ButtonPress.LONG
            ),
        },
        {
            "bit": 5,
            "cb_short": lambda: expanderbutton.ButtonPress.handle_press(
                expanderbutton.ButtonPress.BUTTON_DOWN, expanderbutton.ButtonPress.SHORT
            ),
            "cb_long": lambda: expanderbutton.ButtonPress.handle_press(
                expanderbutton.ButtonPress.BUTTON_DOWN, expanderbutton.ButtonPress.LONG
            ),
        },
    ]

    try:
        i2c = machine.I2C(0, scl=machine.Pin(I2C_SCL_PIN), sda=machine.Pin(I2C_SDA_PIN))
        irq_pin = machine.Pin(BUTTON_EXPANDER_PIN, machine.Pin.IN, None)
        button_expander = expanderbutton.uButtonExpander(i2c, BUTTON_EXPANDER_I2C_ADDRESS, irq_pin, buttons)
    except Exception as e:
        _exception_handler(None, {"exception": expanderbutton.ExpanderButtonException("There seems to be a hardware issue. Try another USB port.")})
    
    return button_expander


def _setup_uart_serial():
    uart = machine.UART(
        1,
        baudrate=9600,
        bits=8,
        stop=1,
        parity=0,
        tx=machine.Pin(SERIAL_TX_PIN, machine.Pin.OUT),
        rx=machine.Pin(SERIAL_RX_PIN, machine.Pin.IN),
    )
    return uart


def startup():
    async def _task_gc_collect():
        while True:
            gc.collect()
            await asyncio.sleep(1)

    async def _task_boot(eink):
        _textwriter = textwriter.TextWriter(eink, _fonts_regular, _fonts_bold)

        theme_font = _fonts_bold[16]
        _textwriter.write_text_center("Security Samurai", theme_font, 35)

        eink.fb.blit(make_image("ctc2025", 126, 18), 13, 10)
        eink.fb.blit(make_image("ctcicon", 54, 53), 49, 65)
        
        try:
            eink.fb.blit(make_image(f"team{get_team_id()}", 152, 32), 0, 151-32)
        except:
            eink.fb.blit(make_image("flowers", 152, 16), 0, 151-16)
        
        _textwriter.write_text_center("Security Samurai", theme_font, 35)
        
        await eink.display()
        await asyncio.sleep(0.5)
        
    # fmt: off
    print("""
 _____                                                                _____ 
( ___ )                                                              ( ___ )
 |   |~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|   | 
 |   |  ██████╗████████╗ ██████╗    ██████╗  ██████╗ ██████╗ ███████╗ |   | 
 |   | ██╔════╝╚══██╔══╝██╔════╝    ╚════██╗██╔═████╗╚════██╗██╔════╝ |   | 
 |   | ██║        ██║   ██║          █████╔╝██║██╔██║ █████╔╝███████╗ |   | 
 |   | ██║        ██║   ██║         ██╔═══╝ ████╔╝██║██╔═══╝ ╚════██║ |   | 
 |   | ╚██████╗   ██║   ╚██████╗    ███████╗╚██████╔╝███████╗███████║ |   | 
 |   |  ╚═════╝   ╚═╝    ╚═════╝    ╚══════╝ ╚═════╝ ╚══════╝╚══════╝ |   |
 |   |                     ~~ SECURITY SAMURAIS ~~                    |   |  
 |___|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|___| 
(_____)                                                              (_____)
""")

    print("")
    # fmt: on

    button_expander = _setup_button_expander()

    eink = _setup_eink_screen()
    uart = _setup_uart_serial()

    loop = asyncio.get_event_loop()
    _ = loop.create_task(_task_gc_collect())

    _ = loop.create_task(button_expander.run())
    boot_promise = loop.create_task(_task_boot(eink))
    _ = loop.create_task(task_menu(boot_promise, eink, uart))
    _ = loop.create_task(task_serial_send(uart))

    loop.set_exception_handler(_exception_handler)
    loop.run_forever()