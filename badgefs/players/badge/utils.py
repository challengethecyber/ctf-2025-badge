import esp32
import micropython
import os
import re
import time
import ubinascii
import framebuf
import network

import microfont

DEBUG = micropython.const(False)

_nvs = esp32.NVS("badge")

_fonts_cache = {}

SHARES_KEY = "shares"
MAX_SHARES = 3
SHARE_SIZE = 17  # 1 byte for index + 16 bytes for actual share
BLOB_SIZE = SHARE_SIZE * MAX_SHARES
RESERVED_SLOTS = 1

def load_fonts(name="hack"):
    if name in _fonts_cache:
        if DEBUG:
            print_output(f"{__name__}.load_fonts", f'Returning cached font "{name}"')
        return _fonts_cache[name]

    returned_fonts = {}
    regex = re.compile(f"{name}\.(\d*).mfnt")

    for entry in os.listdir("/fonts/"):
        match = regex.match(entry)

        if match is not None:
            returned_fonts[int(match.group(1))] = microfont.MicroFont(
                f"/fonts/{name}.{match.group(1)}.mfnt", cache_index=True
            )

    _fonts_cache[name] = returned_fonts
    return returned_fonts


def get_team_id(include_uid=False, printable=False):
    mac = network.WLAN(0).config('mac')
    mid = mac[3:5]
    if b'0' <= mid[0:1] <= b'9' and b'0' <= mid[1:2] <= b'9' and b'0' <= mac[5:] <= b'9':
        tid = int(mid)
        uid = int(mac[5:])
    else:
        if printable:
            tid = '??'
            uid = '?'
        else:
            tid = 0
            uid = 0
        
    if not printable:
        return tid
    
    if include_uid:
        return f"BT{tid}.{uid}"
    else:
        return f"BT{tid}"

def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False

def store_received_share(share_data):
    if len(share_data) != SHARE_SIZE:
        raise ValueError(f"Share data must be {SHARE_SIZE} bytes")
    
    # Get the new share's index
    new_index = share_data[0]
    
    # Prepare buffer for existing shares blob
    current_blob = bytearray(BLOB_SIZE)
    
    try:
        # Try to get existing shares blob
        _nvs.get_blob(SHARES_KEY, current_blob)
        
        # Check if a share with the same index already exists
        for i in range(MAX_SHARES):
            offset = i * SHARE_SIZE
            if current_blob[offset] == new_index and current_blob[offset] != 0:
                # Share with this index already exists, ignore the new one
                return
    except OSError:
        # No blob exists yet, we'll use the initialized empty buffer
        pass
    
    # Shift existing incoming shares (leaving the first slot untouched)
    for i in range((MAX_SHARES - 1) * SHARE_SIZE - 1, RESERVED_SLOTS * SHARE_SIZE - 1, -1):
        current_blob[i + SHARE_SIZE] = current_blob[i]
    
    # Insert new share at the beginning of the incoming shares section
    offset = RESERVED_SLOTS * SHARE_SIZE
    for i in range(SHARE_SIZE):
        current_blob[offset + i] = share_data[i]
    
    # Store the updated blob
    _nvs.set_blob(SHARES_KEY, current_blob)
    _nvs.commit()

def get_shares():
    shares = []
    
    # Prepare buffer for reading blob
    blob = bytearray(BLOB_SIZE)
    
    try:
        # Get the shares blob
        _nvs.get_blob(SHARES_KEY, blob)
        
        # Extract each share from the blob
        for i in range(MAX_SHARES):
            offset = i * SHARE_SIZE
            # Check if the share exists (index byte != 0)
            if blob[offset] != 0:
                idx = blob[offset]
                actual_share = blob[offset+1:offset+SHARE_SIZE]
                shares.append((idx, actual_share))
    except OSError:
        # No blob exists yet
        pass
    
    return shares

def get_own_share():
    shares = get_shares()
    if len(shares) == 0:
        return b"\x00"*17 # fail
    return (b"%02x" % shares[0][0]) + ubinascii.hexlify(shares[0][1])

def parse_share_hex(share_hex):
    """
    Parse a share from its hex representation.
    
    Args:
        share_hex (str): Hex string of the share (34 characters)
    
    Returns:
        bytes: 17-byte share data
    """
    if len(share_hex) != 34:
        raise ValueError("Share hex must be 34 characters")
    
    return ubinascii.unhexlify(share_hex)

def clear_shares():
    try:
        _nvs.erase_key(SHARES_KEY)
        _nvs.commit()
    except OSError:
        pass


def set_darkmode(darkmode=True):
    _nvs.set_i32("darkmode", int(darkmode))
    _nvs.commit()

    return darkmode


def get_darkmode():
    try:
        darkmode = bool(_nvs.get_i32("darkmode"))
    except OSError:
        darkmode = set_darkmode(False)

    return darkmode


def print_output(name, value):
    print(f"[{time.ticks_ms()}] {name}: {value}")


def benchmark_start():
    return time.ticks_ms()


def benchmark_print(name, value, time_start):
    print_output(name, f"{value}: {time.ticks_ms() - time_start}ms")


def make_image(name, w, h, invert=False):
    buf = bytearray(open(f"/img/{name}.fb", "rb").read())
    if invert:
        for i in range(len(buf)):
            buf[i] = ~buf[i] & 0xFF
    fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)
    return fb
