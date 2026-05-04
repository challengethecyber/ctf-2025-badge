import gc
gc.enable()

import micropython
micropython.alloc_emergency_exception_buf(100)

from badge.main import startup
startup()