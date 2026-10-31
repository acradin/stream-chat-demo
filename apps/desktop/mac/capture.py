"""macOS 14+ screenshots through ScreenCaptureKit, never a desktop fallback."""
import os
import platform
import threading
import time

from apps.desktop.capture_types import WindowSource


def _frameworks():
    if int((platform.mac_ver()[0] or "0").split(".")[0]) < 14:
        raise ValueError("Mac 화면 캡처에는 macOS 14 Sonoma 이상이 필요합니다.")
    try:
        import Quartz
        import ScreenCaptureKit
    except ImportError:
        raise ValueError("Mac 의존성을 설치해주세요: apps/desktop/mac/requirements.txt") from None
    return Quartz, ScreenCaptureKit


def _complete(start, timeout=15):
    """Bound asynchronous Apple APIs; keep Cocoa responsive on the UI thread."""
    done, result = threading.Event(), []
    def callback(value, error):
        result.extend((value, error))
        done.set()
    start(callback)
    deadline = time.monotonic() + timeout
    while not done.is_set():
        if time.monotonic() >= deadline:
            raise ValueError("화면 캡처 응답이 없습니다. 화면 기록 권한을 확인한 뒤 다시 시도해주세요.")
        if threading.current_thread() is threading.main_thread():
            from Foundation import NSDate, NSRunLoop
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(.02))
        else:
            done.wait(.05)
    if result[1] is not None or result[0] is None:
        raise ValueError("화면을 가져오지 못했습니다. 화면 기록 권한과 선택한 창을 확인해주세요.")
    return result[0]


def _shareable_content():
    quartz, kit = _frameworks()
    if not quartz.CGPreflightScreenCaptureAccess():
        quartz.CGRequestScreenCaptureAccess()
        raise ValueError("시스템 설정 → 개인정보 보호 및 보안 → 화면 및 시스템 오디오 기록에서 tiki를 허용한 뒤 앱을 다시 실행해주세요.")
    return _complete(lambda callback: kit.SCShareableContent
                     .getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(True, True, callback))


def _source(window):
    owner = window.owningApplication()
    if owner is None or owner.processID() == os.getpid() or window.windowLayer() != 0:
        return None
    title = str(window.title() or "").strip()
    if not title or window.frame().size.width <= 0 or window.frame().size.height <= 0:
        return None
    return WindowSource(int(window.windowID()), int(owner.processID()), title)


def list_windows():
    return sorted((source for window in _shareable_content().windows()
                   if (source := _source(window)) is not None), key=lambda source: source.title.casefold())


def _jpeg(image, quality):
    from Foundation import NSMutableData
    import Quartz
    data = NSMutableData.data()
    destination = Quartz.CGImageDestinationCreateWithData(data, "public.jpeg", 1, None)
    if destination is None:
        raise ValueError("화면 이미지를 변환할 수 없습니다.")
    Quartz.CGImageDestinationAddImage(destination, image, {Quartz.kCGImageDestinationLossyCompressionQuality: quality})
    if not Quartz.CGImageDestinationFinalize(destination):
        raise ValueError("화면 이미지를 변환할 수 없습니다.")
    return bytes(data)


def _capture(content_filter, width, height, limit, quality):
    _, kit = _frameworks()
    scale = min(1, limit / max(width, height, 1))
    config = kit.SCStreamConfiguration.alloc().init()
    config.setWidth_(max(1, round(width * scale)))
    config.setHeight_(max(1, round(height * scale)))
    config.setShowsCursor_(False)
    config.setCapturesAudio_(False)
    if hasattr(config, "setIgnoreShadowsSingleWindow_"):
        config.setIgnoreShadowsSingleWindow_(True)
    image = _complete(lambda callback: kit.SCScreenshotManager
                      .captureImageWithFilter_configuration_completionHandler_(content_filter, config, callback))
    return _jpeg(image, quality)


def capture_window(source):
    _, kit = _frameworks()
    windows = _shareable_content().windows()
    window = next((window for window in windows if _source(window) == source), None)
    # A title may change during streaming; identity is the window ID AND PID.
    if window is None:
        window = next((window for window in windows if (item := _source(window)) is not None
                       and (item.handle, item.pid) == (source.handle, source.pid)), None)
    if window is None:
        raise ValueError("선택한 창이 닫히거나 최소화됐습니다. 창을 다시 선택해주세요.")
    content_filter = kit.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
    size = window.frame().size
    return _capture(content_filter, size.width, size.height, 1280, .75)


def capture_primary_screen():
    quartz, kit = _frameworks()
    content = _shareable_content()
    display = next((display for display in content.displays()
                    if display.displayID() == quartz.CGMainDisplayID()), None)
    if display is None:
        raise ValueError("주 모니터를 찾을 수 없습니다.")
    excluded = [window for window in content.windows() if window.owningApplication() is not None
                and window.owningApplication().processID() == os.getpid()]
    content_filter = kit.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, excluded)
    return _capture(content_filter, display.width(), display.height(), 1536, .85)
