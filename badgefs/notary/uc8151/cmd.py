import micropython

"""
Commands are executed putting the DC line in command mode
and sending the command as first byte, followed if needed by
the data arguments (but with DC in data mode).
"""

CMD_PSR = micropython.const(0x00)  # Panel settings
CMD_PWR = micropython.const(0x01)  # Power settings
CMD_POF = micropython.const(0x02)  # Power off
CMD_PFS = micropython.const(0x03)  # Power off sequence settings
CMD_PON = micropython.const(0x04)  # Power on
CMD_PMES = micropython.const(0x05)  # Power on measure
CMD_BTST = micropython.const(0x06)  # Boot soft-start
CMD_DSLP = micropython.const(0x07)  # Deep sleep
CMD_DTM1 = micropython.const(0x10)  # Display start transmission 1 (white/black data)
CMD_DSP = micropython.const(0x11)  # Data stop
CMD_DRF = micropython.const(0x12)  # Display refresh
CMD_DTM2 = micropython.const(0x13)  # Display start transmission 2 (red data)
CMD_LUT_VCOM = micropython.const(0x20)  # LUT VCOM
CMD_LUT_WW = micropython.const(0x21)  # LUT white-white
CMD_LUT_BW = micropython.const(0x22)  # LUT black-white
CMD_LUT_WB = micropython.const(0x23)  # LUT white-black
CMD_LUT_BB = micropython.const(0x24)  # LUT black-black
CMD_PLL = micropython.const(0x30)  # PPL control
CMD_TSC = micropython.const(0x40)  # Temperature sensor calibration
CMD_TSE = micropython.const(0x41)  # Temperature sensor selection
CMD_TSW = micropython.const(0x42)  # Temperature sensor write
CMD_TSR = micropython.const(0x43)  # Temperature sensor read
CMD_CDI = micropython.const(0x50)  # VCOM and data interval settings
CMD_LPD = micropython.const(0x51)  # Low power detection
CMD_TCON = micropython.const(0x60)  # TCON settings
CMD_TRES = micropython.const(0x61)  # Resolution settings
CMD_GSST = micropython.const(0x65)  # GSST settings
CMD_REV = micropython.const(0x70)  # Revision
CMD_FLG = micropython.const(0x71)  # Get status
CMD_AMV = micropython.const(0x80)  # Auto measurement
CMD_VV = micropython.const(0x81)  # Read VCOM value
CMD_VDCS = micropython.const(0x82)  # VCOM_DC settings
CMD_PTL = micropython.const(0x90)  # Partial window
CMD_PTIN = micropython.const(0x91)  # Partial in
CMD_PTOU = micropython.const(0x92)  # Partial out
CMD_PGM = micropython.const(0xA0)  # Program mode
CMD_APG = micropython.const(0xA1)  # Active programming
CMD_ROTP = micropython.const(0xA2)  # Read OTP
CMD_CCSET = micropython.const(0xE0)  # Cascase settings
CMD_PWS = micropython.const(0xE3)  # Power savings
CMD_LPSEL = micropython.const(0xE4)  # LDP selection
CMD_TSSET = micropython.const(0xE5)  # Force temperature
