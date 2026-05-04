import framebuf
import micropython
import time

BENCHMARK = micropython.const(False)


def benchmark_start():
    return time.ticks_ms()


def benchmark_print(name, value, time_start):
    print_output(name, f"{value}: {time.ticks_ms() - time_start}ms")


def print_output(name, value):
    print(f"[{time.ticks_ms()}] {name}: {value}")


class TextWriter:
    def __init__(self, eink, fonts, fonts_bold):
        self._eink = eink
        self._fonts = fonts
        self._fonts_bold = fonts_bold

    def write_text_center(self, text, font, start_y, inverted=False):
        if BENCHMARK:
            _benchmark = benchmark_start()

        len_text = len(text) * font.max_width
        screen_center = self._eink.width / 2
        start_x = int(screen_center - (len_text / 2))
        font.write(
            text,
            self._eink.buffer,
            framebuf.MONO_HLSB,
            self._eink.width,
            self._eink.height,
            start_x,
            start_y,
            0 if inverted else 1,
            rot=0,
            x_spacing=0,
            y_spacing=0,
        )

        if BENCHMARK:
            benchmark_print(__name__, "write_text_center", _benchmark)

    def write_text(self, text, font, start_x, start_y, inverted=False):
        if BENCHMARK:
            _benchmark = benchmark_start()

        font.write(
            text,
            self._eink.buffer,
            framebuf.MONO_HLSB,
            self._eink.width,
            self._eink.height,
            start_x,
            start_y,
            0 if inverted else 1,
            rot=0,
            x_spacing=0,
            y_spacing=0,
        )

        if BENCHMARK:
            benchmark_print(__name__, "write_text", _benchmark)

    def get_right_size(self, text, max_size=100, bold=False):
        if BENCHMARK:
            _benchmark = benchmark_start()

        width = 0
        current_font = None
        WIDTH_INDEX = 2

        fonts = self._fonts if not bold else self._fonts_bold

        for height, font in fonts.items():
            if height <= max_size:
                new_width = sum([font.get_ch(t)[WIDTH_INDEX] for t in text])

                if new_width <= 152 - 4 and new_width > width:
                    width = new_width
                    current_font = font

        if current_font is None:
            raise Exception("Could not find proper font")

        if BENCHMARK:
            benchmark_print(__name__, "get_right_size", _benchmark)

        return current_font
