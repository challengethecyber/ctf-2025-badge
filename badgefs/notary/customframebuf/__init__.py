import framebuf


class CustomFrameBuffer(framebuf.FrameBuffer):
    """
    Adds extra functionality to the MicroPython FrameBuffer, such as storing
    the width, the height, exposing the raw buffer, and offering a rotation
    function.
    """

    def __init__(self, buffer, width, height):
        self._width = width
        self._height = height

        super().__init__(buffer, width, height, framebuf.MONO_HLSB, width)

    def rotate(self, target_buffer):
        """Rotates the framebuffer and writes it to target_buffer."""
        try:
            # Check if there is a native function written in C (faster).
            super().rotate(target_buffer)
            return
        except AttributeError:
            # If not, rotate in Python.
            target_framebuffer = framebuf.FrameBuffer(target_buffer, self._width, self._height, framebuf.MONO_HLSB)

            for x in range(self._width):
                for y in range(self._height):
                    target_framebuffer.pixel(y, x, self.pixel(x, y))
