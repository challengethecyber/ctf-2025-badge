import network
import espnow
from time import sleep
import micropython
import uc8151
import machine
import asyncio

EINK_CS_PIN = micropython.const(5)
EINK_DC_PIN = micropython.const(4)
EINK_RST_PIN = micropython.const(10)
EINK_BUSY_PIN = micropython.const(3)
EINK_SCK_PIN = micropython.const(6)
EINK_MOSI_PIN = micropython.const(7)
EINK_SPEED = micropython.const(4)

eink = uc8151.UC8151(
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
        darkmode=False,
    )

eink.fb.fill(0)
eink.fb.text('NOTARY', 10, 10, 0x1)
asyncio.run(eink.display())

width, height = 152, 152
x, y = 10, 20
padding = 5
rect_size = 5

def draw_next_rectangle():
    global x, y

    # If the current position exceeds the screen dimensions, restart
    if y + rect_size > height:
        # Machine Reset
        machine.reset()
        return

    # Draw the rectangle
    eink.fb.rect(x, y, rect_size, rect_size, 1)  # 1 for color (white)
    asyncio.run(eink.display())

    # Move to the next horizontal position
    x += rect_size + padding

    # If horizontal space is exhausted, move to the next row
    if x + rect_size > width:
        x = 10  # Reset x position to start
        y += rect_size + padding


WIFI_PROTOCOL_LR = 8

wlan = network.WLAN(network.WLAN.IF_STA)
wlan.active(True)
wlan.config(channel=6)
wlan.config(mac=b"NOTARY")
wlan.config(pm=network.WLAN.PM_NONE)
wlan.config(protocol=WIFI_PROTOCOL_LR)

e = espnow.ESPNow()

peer = b'\xff\xff\xff\xff\xff\xff'

while True:
    try:
        draw_next_rectangle()
        e.send(peer, b'\x00')
        sleep(1.5)
    except OSError as err:
        if len(err.args) < 2:
            machine.reset()
        if err.args[1] == 'ESP_ERR_ESPNOW_NOT_INIT':
            e.active(True)
        elif err.args[1] == 'ESP_ERR_ESPNOW_NOT_FOUND':
            e.add_peer(peer)
        elif err.args[1] == 'ESP_ERR_ESPNOW_IF':
            network.WLAN(network.WLAN.IF_STA).active(True)
        else:
            machine.reset()
    except:
        machine.reset()
