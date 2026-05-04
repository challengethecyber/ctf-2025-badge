import json
import micropython
import os
import requests

import textwriter

from .base_app import BaseApp
from .utils import load_fonts, print_output, make_image, get_team_id, file_exists

DEBUG = micropython.const(False)


class Nametag(BaseApp):

    def __init__(self, eink, text_writer, tag_name, tag_avatar, tag_team, **kwargs):
        super().__init__(eink=eink, max_index=5, **kwargs)

        self._text_writer = text_writer
        self._tag_name = tag_name
        self._tag_avatar = tag_avatar
        self._tag_team = tag_team
        self._first_draw = False
        self._current_index = max(0, min(5, tag_avatar - 1))
        self._has_drawn = False

    async def _draw(self):
        self._eink.fb.fill(0)
        self._tag_avatar = self._current_index + 1
                
        if self._has_drawn:
            info_json = {"name": self._tag_name, "avatar": self._tag_avatar, "team": self._tag_team}
            with open(f"/tags/mytag.json", "wb") as tag_stream:
                json.dump(info_json, tag_stream)
            os.sync()
        else:
            self._has_drawn = True
                   
        self._text_writer.write_text_center(self._tag_name, self._text_writer._fonts_bold[24], 20)
        
        try:
            img_team = make_image(f"team{self._tag_team}", 152, 32)
            self._eink.fb.blit(img_team, 0, 44)
        except:
            self._text_writer.write_text_center(f"Team {self._tag_team}", self._text_writer._fonts[20], 50)

        if 1 <= self._tag_avatar <= 6:
            img_avatar = make_image(f"samu{self._tag_avatar}", 64, 64)
            self._eink.fb.blit(img_avatar, 152 // 2 - 64 // 2, 87)
        else:
            img_avatar = make_image(f"cat", 55, 64)
            self._eink.fb.blit(img_avatar, 152 // 2 - 55 // 2, 87)

        if not self._has_drawn:
            self._has_drawn = True

        await super()._draw()

    @staticmethod
    def has_vfs():
        if Nametag.get_vfs():
            return True
        else:
            return False

    @staticmethod
    def get_vfs():
        try:
            with open(f"/tags/mytag.json", "rb") as tag_fh:
                tag_bin = tag_fh.read()
            return json.loads(tag_bin)
        except OSError:
            return None

    @classmethod
    def from_vfs(cls, eink, fonts_regular, fonts_bold):
        if json_tag := cls.get_vfs():
            tag_name = json_tag["name"]
            tag_avatar = json_tag["avatar"]
        else:
            tag_name = "Hacker"
            tag_avatar = 1
        
        tag_team = get_team_id()

        return cls(
            eink,
            textwriter.TextWriter(eink, fonts_regular, fonts_bold),
            tag_name,
            tag_avatar,
            tag_team
        )

    @staticmethod
    def get_binary_tag_for_exchange():
        if json_tag := Nametag.get_vfs():
            tag_name = json_tag["name"]
            tag_avatar = json_tag["avatar"]
        else:
            tag_name = "Hacker"
            tag_avatar = 1
        
        tag_team = get_team_id()
        return json.dumps({"name": tag_name, "avatar": tag_avatar, "team": tag_team}).encode()


async def app_nametag(eink, **kwargs):
    fonts_regular = load_fonts("hack")
    fonts_bold = load_fonts("hackbold")

    tag = Nametag.from_vfs(eink=eink, fonts_regular=fonts_regular, fonts_bold=fonts_bold)
    await tag.main()
