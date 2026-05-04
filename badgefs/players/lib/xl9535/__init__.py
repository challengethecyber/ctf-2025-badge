from micropython import const


XL9535_INPUT_PORT0 = const(0x00)
XL9535_INPUT_PORT1 = const(0x01)
XL9535_OUTPUT_PORT0 = const(0x02)
XL9535_OUTPUT_PORT1 = const(0x03)
XL9535_INVERSION_PORT0 = const(0x04)
XL9535_INVERSION_PORT1 = const(0x05)
XL9535_CONFIG_PORT0 = const(0x06)
XL9535_CONFIG_PORT1 = const(0x07)

CTC_BADGE2025_EEPROM_WP_PORT = const(0)
CTC_BADGE2025_GPIO1_PORT = const(1)
CTC_BADGE2025_GPIO2_PORT = const(2)


class XL9535(object):
    def __init__(self, i2c, address=0x26):
        self._i2c = i2c
        self._address = address
        self._output_buffer = bytearray(1)

    def check(self):
        if self._i2c.scan().count(self._address) == 0:
            raise OSError(f"XL9535 not found at I2C address {self._address:#x}")

        return True

    def init(self):
        self._output_buffer[0] = 0x00  # Configure as output

        # set inversion off so reading INPUT_PORTx reads the same as OUTPUT_PORTx
        # saves having to XOR (n ^ 0xff) to invert on each read
        # self._i2c.writeto_mem(
        #     self._address, XL9535_INVERSION_PORT1, self._output_buffer
        # )

        # all relays (outputs) off (NC<->COM-x-NO), blue LED off
        # high bit means relay on (NC-x-COM<->NO), blue LED on
        self._i2c.writeto_mem(self._address, XL9535_OUTPUT_PORT0, self._output_buffer)

        # all circuits (configs) enabled
        # low bit means enabled
        self._i2c.writeto_mem(self._address, XL9535_CONFIG_PORT0, self._output_buffer)

    def set_eeprom_wp(self, value):
        self._set_output_port(CTC_BADGE2025_EEPROM_WP_PORT, value)

    def set_sao_gpio1(self, value):
        self._set_output_port(CTC_BADGE2025_GPIO1_PORT, value)

    def set_sao_gpio2(self, value):
        self._set_output_port(CTC_BADGE2025_GPIO2_PORT, value)

    # Set an output value
    def _set_output_port(self, num, value):
        assert 0 <= num <= 2, "num should be in range 0-2"

        b = 1 << (num % 8)

        self._i2c.readfrom_mem_into(self._address, XL9535_OUTPUT_PORT0, self._output_buffer)

        # Set output status
        self._output_buffer[0] &= ~b  # unset bit
        if value:
            self._output_buffer[0] |= b  # reset bit

        self._i2c.writeto_mem(self._address, XL9535_OUTPUT_PORT0, self._output_buffer)
