import asyncio
import micropython
import cryptolib
import hashlib
import binascii
import os
import json

import expanderbutton
import textwriter

from .base_app import BaseApp

from .nametag import Nametag
from .utils import load_fonts, get_shares, store_received_share, get_own_share, parse_share_hex, make_image

from shamirss import ShamirSS

SERIAL_START = micropython.const(b"<message>")
SERIAL_STOP = micropython.const(b"</message>")

class Rolodex(BaseApp):
    def __init__(
        self,
        eink,
        header_font,
        contacts_num_font,
        contacts_entry_font,
        social_flag_font,
        overlay_key_font,
        overlay_val_font,
        text_writer,
        **kwargs,
    ):
        self._cached_tag_jsons = Rolodex.list_tag_jsons()
        self._cached_tag_num = len(self._cached_tag_jsons)

        super().__init__(eink=eink, max_index=self._cached_tag_num - 1, **kwargs)

        self._text_writer = text_writer
        self._header_font = header_font
        self._contacts_num_font = contacts_num_font
        self._social_flag_font = social_flag_font
        self._contacts_entry_font = contacts_entry_font
        self._overlay_key_font = overlay_key_font
        self._overlay_val_font = overlay_val_font
        self._current_index = self._cached_tag_num - 1
        self._first_draw = False

    async def _draw_header(self):
        rolo_rect_padding = 2
        rolo_rect_height = self._header_font.height + rolo_rect_padding
        rolo_rect_margin = 2

        self._eink.fb.rect(0, 0, self._eink.width, self._header_font.height + rolo_rect_padding, 1, True)

        current_y = rolo_rect_padding // 2
        self._text_writer.write_text_center(
            "ROLODEX",
            self._header_font,
            current_y,
            True,  # Inverted
        )

        current_y = rolo_rect_height + rolo_rect_margin
        return current_y

    async def _draw_social(self):
        social_flag_parts = len(get_shares())
        if social_flag_parts == 3:
            flag_text = self.get_social_flag()
            if not flag_text:
                social_flag_msg = "FAILED"
            else:
                social_flag_msg = flag_text
        else:
            social_flag_msg = f"{social_flag_parts}/3 unique parts"

        social_text_height = self._social_flag_font.height * 2

        social_rect_padding = 6
        social_rect_height = social_text_height + social_rect_padding
        social_rect_margin = 2

        self._eink.fb.rect(
            0,
            self._eink.height - (social_text_height + social_rect_padding) - 1,
            self._eink.width,
            social_text_height + social_rect_padding,
            1,
            False,
        )

        current_y = self._eink.height - social_text_height - social_rect_padding // 2

        self._text_writer.write_text_center("Social flag:", self._social_flag_font, current_y)

        current_y += self._social_flag_font.height

        self._text_writer.write_text_center(social_flag_msg, self._social_flag_font, current_y)

    async def _draw(self):
        self._eink.fb.fill(0)

        current_y = await self._draw_header()

        if self._cached_tag_num == 0:
            text_padding = 8
            current_y += text_padding

            self._text_writer.write_text("No contacts in\nthe rolodex yet!", self._header_font, 3, current_y)
            current_y += self._header_font.height * 2 + text_padding

            self._text_writer.write_text("Connect to others\n...and get a flag!", self._header_font, 3, current_y)

        else:
            text_padding = 2
            current_y += text_padding

            self._text_writer.write_text_center(
                f"Contact {self._current_index+1}/{self._max_index+1}", self._contacts_num_font, current_y
            )
            current_y += self._header_font.height + text_padding

            name, avatar, team = self.get_current_tag()

            self._text_writer.write_text_center(name, self._contacts_entry_font, current_y)
            current_y += self._header_font.height
            
            try:
                img_team = make_image(f"team{team}", 152, 32)
                self._eink.fb.blit(img_team, 0, 50)
            except:
                self._text_writer.write_text_center(f"Team {team}", self._text_writer._fonts[18], 50)
                
            if 1 <= avatar <= 6:
                img_avatar = make_image(f"samu{avatar}", 64, 64)
                self._eink.fb.blit(img_avatar, 152 // 2 - 64 // 2, 86)
            else:
                img_avatar = make_image(f"cat", 55, 68)
                self._eink.fb.blit(img_avatar, 152 // 2 - 55 // 2, 86)

            self._eink.fb.rect(
                0,
                120,
                152,
                32,
                0,
                True,
            )

        await self._draw_social()
        await super()._draw()

    async def _draw_overlay(self, shh_message, tag_message):
        self._eink.fb.fill(0)

        current_y = await self._draw_header()

        self._eink.fb.rect(0, self._header_font.height + 5, self._eink.width, 95, 1, True)
        current_y = self._header_font.height + 20

        self._eink.fb.rect(10, self._header_font.height + 15, self._eink.width - 20, 95 - 20, 0, True)

        self._text_writer.write_text_center("Tag exchange:", self._overlay_key_font, current_y)
        current_y += self._overlay_key_font.height

        self._text_writer.write_text_center(tag_message, self._overlay_val_font, current_y)
        current_y += self._overlay_val_font.height + 5

        self._text_writer.write_text_center("Social flag:", self._overlay_key_font, current_y)
        current_y += self._overlay_key_font.height

        self._text_writer.write_text_center(shh_message, self._overlay_val_font, current_y)
        current_y += self._overlay_val_font.height

        await self._draw_social()
        await self._eink.display()

        self._cached_tag_jsons = Rolodex.list_tag_jsons()
        self._cached_tag_num = len(self._cached_tag_jsons)
        self._max_index = self._cached_tag_num - 1
        self._current_index = self._cached_tag_num - 1

        await asyncio.sleep(7)
        self._draw_event.set()

    async def main(self):
        loop = asyncio.get_event_loop()

        super_task = loop.create_task(super(Rolodex, self).main())
        serial_task = loop.create_task(self.task_serial_recv())

        await super_task

        try:
            serial_task.cancel()
        except asyncio.CancelledError:
            pass

    async def task_serial_recv(self):
        backoff_wait = False
        loop = asyncio.get_event_loop()

        if self._uart.any():
            self._uart.read()

        while True:
            if self._uart.any():
                incoming_data = self._uart.read().strip(b"\n")
                if incoming_data.startswith(SERIAL_START) and (data_end := incoming_data.find(SERIAL_STOP)) >= 0:
                    actual_data = incoming_data[len(SERIAL_START) : data_end]

                    try:
                        decoded_data = binascii.a2b_base64(actual_data)
                        await loop.create_task(self.data_processor(decoded_data))
                        backoff_wait = True
                    except ValueError:
                        pass

            if backoff_wait:
                await asyncio.sleep(13)
                if self._uart.any(): self._uart.read()
                backoff_wait = False
        
            await asyncio.sleep(2)
        
    async def data_processor(self, data):
        shh_data, tag_data = data[:34], data[34:]

        tag_message = await self.process_incoming_tag(tag_data)
        shh_message = await self.process_incoming_shh(shh_data)

        await self._draw_overlay(shh_message, tag_message)

    async def process_incoming_tag(self, tag_data):
        if not tag_data or len(tag_data) == 0 or len(tag_data) > 4096:
            return "FAIL"

        tag_hash = Rolodex.get_tag_hash(tag_data)

        if Rolodex.has_tag_hash(tag_hash):
            return "ALREADY PRESENT"

        Rolodex.add_tag(tag_hash, tag_data)
        return "ADDED!"

    async def process_incoming_shh(self, shh_data):
        shh_parts_before = len(get_shares())
        store_received_share(parse_share_hex(shh_data))
        shh_parts_after = len(get_shares())

        if shh_parts_after == 3:
            shh_message = "GRATZ!"
        elif shh_parts_after <= shh_parts_before:
            shh_message = "NO NEW PARTS"
        else:
            shh_message = "NEW PART!"

        return shh_message

    def get_social_flag(self):
        secret = None
        try:
            secret = ShamirSS.reconstruct_secret(get_shares())
        except Exception as e:
            print("shamir fail", e)
            return False
        
        def is_valid_flag(b):
            return all((65 <= c <= 90) or (97 <= c <= 122) or c == 95 for c in b)
        
        if secret and is_valid_flag(secret):
            return secret.decode()
            
        return False

    def get_current_tag(self):
        tag_num, tag_hash = self._cached_tag_jsons[self._current_index]

        with open(f"/tags/rolodex.{tag_num}.{tag_hash}.json", "rb") as tag_fh:
            try:
                tag_json = json.load(tag_fh)
                tag_name = str(tag_json.get("name", ""))
                tag_avatar = int(tag_json.get("avatar", 1))
                tag_team = int(tag_json.get("team", 0))
            except:
                tag_name = "Hacker"
                tag_avatar = 7
                tag_team = 0
                
        return (tag_name, tag_avatar, tag_team, )

    @staticmethod
    def add_tag(tag_hash, tag_data):
        if tag_jsons := Rolodex.list_tag_jsons():
            new_tag_num = max(tag_jsons, key=lambda e: e[0])[0] + 1
        else:
            new_tag_num = 1

        with open(f"/tags/rolodex.{new_tag_num}.{tag_hash}.json", "wb") as tag_fh:
            tag_fh.write(tag_data)
        os.sync()

    @staticmethod
    def list_tag_jsons():
        tag_entries = []

        for t in os.listdir("/tags"):
            if t.startswith("rolodex.") and t.endswith(".json"):
                tag_num, tag_hash = t.split(".", 3)[1:3]
                tag_entries.append((int(tag_num), tag_hash))

        sorted(tag_entries, key=lambda e: e[0])
        return tag_entries

    @staticmethod
    def has_tag_hash(tag_hash):
        for t_num, t_hash in Rolodex.list_tag_jsons():
            if t_hash == tag_hash:
                return True
        return False

    @staticmethod
    def get_tag_hash(tag_data):
        return binascii.hexlify(hashlib.md5(tag_data).digest()[:4]).decode()


async def app_rolodex(eink, **kwargs):
    fonts_regular = load_fonts("hack")
    fonts_bold = load_fonts("hackbold")

    await Rolodex(
        eink=eink,
        header_font=fonts_bold[16],
        contacts_num_font=fonts_regular[12],
        social_flag_font=fonts_regular[12],
        contacts_entry_font=fonts_bold[14],
        overlay_key_font=fonts_bold[16],
        overlay_val_font=fonts_regular[16],
        text_writer=textwriter.TextWriter(eink, fonts_regular, fonts_bold),
        **kwargs,
    ).main()


async def task_serial_send(uart):
    while True:
        outgoing_data = get_own_share() + Nametag.get_binary_tag_for_exchange()
        uart_out_data = SERIAL_START + binascii.b2a_base64(outgoing_data).strip(b"\n") + SERIAL_STOP + b"\n"
        uart.write(uart_out_data)
        await asyncio.sleep(2)
