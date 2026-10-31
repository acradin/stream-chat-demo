import ctypes
from ctypes.util import find_library


def register_font(path):
    library = find_library("fontconfig")
    if not library:
        return False
    api = ctypes.CDLL(library)
    api.FcConfigGetCurrent.restype = ctypes.c_void_p
    api.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p,ctypes.c_char_p]
    api.FcConfigAppFontAddFile.restype = ctypes.c_int
    return bool(api.FcConfigAppFontAddFile(api.FcConfigGetCurrent(),str(path).encode()))
