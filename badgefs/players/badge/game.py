import json
import micropython
import os
import requests
import asyncio
import textwriter
import network
import time
import aioespnow

from .base_app import BaseApp
from .utils import load_fonts, print_output, make_image

DEBUG = micropython.const(False)
WIFI_PROTOCOL_LR = micropython.const(8)

BET_EVEN = micropython.const('EVEN')
BET_ODD = micropython.const('ODD')
BET_NEW_ROUND = micropython.const(b'starting new betting round')
BET_OPEN_BETTING = micropython.const(b'receiving bets now')
BET_RESULT = micropython.const(b'round ended. Result: ')

class Game(BaseApp):
    tag_static_bin = None
    tag_static_json = None

    def __init__(self, eink, header_font, regular_font, streak_font, text_writer, **kwargs):
        super().__init__(eink=eink, max_index=1, **kwargs)

        self._header_font = header_font
        self._regular_font = regular_font
        self._streak_font = streak_font
        self._text_writer = text_writer
        self._first_draw = False
        
        self._game_joined = False
        self._current_index = 0
        self._circular_index = False
        self._current_bet = None
        self._bet_streak = 0
        self._current_round = 0
        self._round_ended = False
        self._bet_sent_ok = False
        self._round_results = (0,0)
        self._game_won = False
        
    async def _draw_header(self):
        hd_rect_padding = 2
        hd_rect_height = self._header_font.height + hd_rect_padding
        hd_rect_margin = 2

        self._eink.fb.rect(0, 0, self._eink.width, self._header_font.height + hd_rect_padding, 1, True)

        current_y = hd_rect_padding // 2
        self._text_writer.write_text_center(
            "CHO-HAN GAME",
            self._header_font,
            current_y,
            True,  # Inverted
        )

        current_y = hd_rect_height + hd_rect_margin
        return current_y

    async def _draw(self):
        self._eink.fb.fill(0)
        current_y = await self._draw_header()
        
        if not self._game_joined:
            self._text_writer.write_text_center(f"Joining game...", self._streak_font, 30)
            self._text_writer.write_text_center(f"This may take 10sec", self._regular_font, 60)
            
            self._text_writer.write_text_center(f"Flag is given for", self._regular_font, 90)
            self._text_writer.write_text_center(f"a lucky streak of", self._regular_font, 102)
            self._text_writer.write_text_center(f"9 in a row!", self._regular_font, 114)

        else:
            if not self._round_ended:
                self._text_writer.write_text_center(f"Place your bets!", self._regular_font, 30)
                
                self._eink.fb.blit(make_image("cat", 55, 64), 30, 55)

                self._eink.fb.rect(110, 65, 42, self._regular_font.height + 10, 1, False)
                self._text_writer.write_text(f"EVEN", self._regular_font, 118, 70)
                
                self._eink.fb.rect(110, 125, 42, self._regular_font.height + 10, 1, False)
                self._text_writer.write_text(f"ODD", self._regular_font, 121, 130)
                    
                if self._current_bet is None:
                    if self._current_index < 0: # EVEN
                        self._current_bet = BET_EVEN
                    elif self._current_index > 0: # ODD
                        self._current_bet = BET_ODD
                
                self._current_index = 0

                if self._current_bet == BET_EVEN:
                    self._eink.fb.rect(110, 65, 42, self._regular_font.height + 10, 1, True)
                    self._text_writer.write_text(f"EVEN", self._regular_font, 118, 70, True)
                if self._current_bet == BET_ODD:
                    self._eink.fb.rect(110, 125, 42, self._regular_font.height + 10, 1, True)
                    self._text_writer.write_text(f"ODD", self._regular_font, 121, 130, True)
                    
                streak_msg = "Flag: ask" if self._game_won else f"Streak: {self._bet_streak}"
            else:
                hdmsg = ""
                dice_a, dice_b = self._round_results
                res = BET_EVEN if sum(self._round_results) % 2 == 0 else BET_ODD
                dice_res_img = "chohan-cho-even" if res == BET_EVEN else "chohan-han-odd"
                
                if self._current_bet and not self._bet_sent_ok:
                    hdmsg = "FAILED bet"
                    self._bet_streak = 0
                elif not self._current_bet:
                    hdmsg = "Too SLOW..."
                    self._bet_streak = 0
                else:
                    if res == self._current_bet:
                        hdmsg = "You WIN!"
                        self._bet_streak += 1
                        if self._bet_streak >= 9:
                            self._game_won = True
                    else:
                        hdmsg = "You LOSE!"
                        self._bet_streak = 0
                
                self._text_writer.write_text_center(hdmsg, self._streak_font, 30)
                
                self._eink.fb.blit(make_image(f"dice{dice_a}", 32, 32), 15, 80)
                self._eink.fb.blit(make_image(f"dice{dice_b}", 32, 32), 15+32+5, 60)
                self._eink.fb.text('+', 55, 98)
                self._eink.fb.text('=', 87, 80)
                self._eink.fb.blit(make_image(dice_res_img, 40, 40), 100, 60)
                self._text_writer.write_text("{:>4}".format(res), self._regular_font, 105, 102)
            
                streak_msg = "Flag: ask coach" if self._game_won else f"Streak: {self._bet_streak}"
            self._text_writer.write_text(streak_msg, self._streak_font, 15, 130)
            
        await super()._draw()
        
    async def task_receive_msgs(self, en):
        while True:
            if en.any():
                async for mac, msg in en:
                    # print(mac, msg)
                    if mac == b'BETBOX':
                        round_num = 0
                        round_msg = b""
                        if msg.startswith(b"Round "):
                            colon_idx = msg.find(b":")
                            if colon_idx != -1:
                                round_num_str = msg[len(b"Round "):colon_idx]
                                try:
                                    round_num = int(round_num_str)
                                except:
                                    pass
                                round_msg = msg[colon_idx+2:]
                        
                        #print(round_msg)
                        if round_num > 0:
                            if round_msg.startswith(BET_NEW_ROUND):
                                self._game_joined = True
                                self._round_ended = False
                            elif round_msg.startswith(BET_OPEN_BETTING):
                                if self._current_round != round_num:
                                    self._current_round = round_num
                                    self._current_bet = None
                                    self._bet_sent_ok = False
                                    self._current_index = 0
                                    self._draw_event.set()
                            elif round_msg.startswith(BET_RESULT):
                                self._round_ended = True
                                
                                dice_a = 0
                                dice_b = 0
                                try:
                                    dice_a = max(1,min(6,int(round_msg[len(BET_RESULT):][:1])))
                                    dice_b = max(1,min(6,int(round_msg[len(BET_RESULT)+3:][:1])))
                                except:
                                    pass
                                    
                                self._round_results = (dice_a, dice_b)
                                self._draw_event.set()
            
            await asyncio.sleep_ms(100)

    async def task_send_msgs(self, en):
        while True:
            if self._current_bet and not self._round_ended and not self._bet_sent_ok:
                try:
                    res = await en.asend(b'BETBOX', f'bet {self._current_bet}')
                    if res:
                        self._bet_sent_ok = True
                except Exception as e:
                    print(e)
            await asyncio.sleep_ms(100)

    async def task_espnow(self):
        try:
            sta_if = network.WLAN(network.STA_IF)
            sta_if.active(True)
            sta_if.config(channel=6)
            sta_if.config(pm=network.WLAN.PM_NONE)
            sta_if.config(protocol=WIFI_PROTOCOL_LR)
            sta_if.disconnect()
        except Exception as e:
            print_output(__name__, f"Wlan err: {str(e)}")
            time.sleep(4)
            machine.reset()
        
        en = aioespnow.AIOESPNow()
        en.active(True)
        en.config(timeout_ms=100)
        try:
            en.add_peer(b'BETBOX')
        except:
            pass
        
        loop = asyncio.get_event_loop()
        await asyncio.gather(
            loop.create_task(self.task_receive_msgs(en)),
            loop.create_task(self.task_send_msgs(en))
            )
        
    async def task_gameserver(self):
        # from .twister import MiniMT27
        # NOTE: Not implemented here. This is implemented by the BETBOX instead.
        pass
                        
    async def main(self):
        loop = asyncio.get_event_loop()

        super_task = loop.create_task(super(Game, self).main())
        espnow_task = loop.create_task(self.task_espnow())

        await super_task

        try:
            espnow_task.cancel()
        except asyncio.CancelledError:
            pass

async def app_game(eink, **kwargs):
    fonts_regular = load_fonts("hack")
    fonts_bold = load_fonts("hackbold")

    await Game(
        eink=eink,
        header_font=fonts_bold[16],
        regular_font=fonts_regular[12],
        streak_font=fonts_regular[14],
        text_writer=textwriter.TextWriter(eink, fonts_regular, fonts_bold),
        **kwargs,
    ).main()

