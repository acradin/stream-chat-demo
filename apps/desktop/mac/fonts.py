"""Process-private CoreText font registration."""


def register_font(path):
    from CoreText import CTFontManagerRegisterFontsForURL, kCTFontManagerScopeProcess
    from Foundation import NSURL
    ok, error = CTFontManagerRegisterFontsForURL(
        NSURL.fileURLWithPath_(str(path)), kCTFontManagerScopeProcess, None)
    return bool(ok) or (error is not None and error.code() == 105)  # AlreadyRegistered.
