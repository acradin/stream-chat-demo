"""Cmd-aware native key monitors. Events are neither recorded nor transmitted."""

MODIFIERS = {"Cmd": 1 << 20, "Ctrl": 1 << 18, "Option": 1 << 19, "Shift": 1 << 17}
KEYS = dict(zip("ASDFHGZXCVBQWERYT123465=97-80]OU[IPLJ'K;\\,/NM.",
                (0,1,2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,37,38,39,40,41,42,43,44,45,46,47)))
# Physical ANSI keys are stable with a Korean input source too.
KEYS.update({"Enter":36, "Tab":48, "Space":49, "Backtick":50, "Backspace":51, "Escape":53,
             "NumDecimal":65, "NumMultiply":67, "NumAdd":69, "NumDivide":75, "NumEnter":76,
             "NumSubtract":78, "Num0":82, "Num1":83, "Num2":84, "Num3":85, "Num4":86,
             "Num5":87, "Num6":88, "Num7":89, "Num8":91, "Num9":92,
             "F1":122, "F2":120, "F3":99, "F4":118, "F5":96, "F6":97, "F7":98,
             "F8":100, "F9":101, "F10":109, "F11":103, "F12":111, "F13":105,
             "F14":107, "F15":113, "F16":106, "F17":64, "F18":79, "F19":80, "F20":90,
             "Home":115, "PageUp":116, "Delete":117, "End":119, "PageDown":121,
             "Left":123, "Right":124, "Down":125, "Up":126})
for symbol, name in {"=":"Equals", "-":"Minus", "[":"BracketLeft", "]":"BracketRight",
                     "'":"Quote", ";":"Semicolon", "\\":"Backslash", ",":"Comma", ".":"Period", "/":"Slash"}.items():
    KEYS[name] = KEYS.pop(symbol)
ALIASES = {name.casefold(): name for name in (*MODIFIERS, *KEYS)}
ALIASES.update({"control":"Ctrl", "alt":"Option", "opt":"Option", "command":"Cmd", "⌘":"Cmd",
                "win":"Cmd", "windows":"Cmd", "super":"Cmd", "return":"Enter", "esc":"Escape",
                "spacebar":"Space", "pgup":"PageUp", "pgdn":"PageDown", "del":"Delete"})
MODIFIER_MASK = sum(MODIFIERS.values())


def parse_hotkey(value):
    if not isinstance(value, str):
        raise ValueError("단축키 조합을 입력해주세요.")
    parts = [ALIASES.get(part.strip().casefold()) for part in value.split("+")]
    keys = [part for part in parts if part not in MODIFIERS]
    if None in parts or len(set(parts)) != len(parts) or len(keys) != 1:
        raise ValueError("단축키를 확인해주세요. 예: Cmd+Shift+G 또는 F8")
    key = keys[0]
    modifiers = [name for name in MODIFIERS if name in parts]
    if not modifiers and not (key.startswith("F") and key[1:].isdigit()):
        raise ValueError("일반 키에는 Cmd/Control/Option/Shift를 함께 눌러주세요.")
    return "+".join([*modifiers, key]), sum(MODIFIERS[name] for name in modifiers), KEYS[key]


def pressed_hotkey(keycode, event=None):
    from AppKit import NSApplication
    native = NSApplication.sharedApplication().currentEvent()
    if native is None:
        return None
    key = next((name for name, code in KEYS.items() if code == native.keyCode()), None)
    if key is None:
        return None
    modifiers = [name for name, mask in MODIFIERS.items() if native.modifierFlags() & mask]
    return parse_hotkey("+".join([*modifiers, key]))[0]


class SingleInstance:
    def __init__(self, state_dir):
        import fcntl
        state_dir.mkdir(parents=True, exist_ok=True)
        self.stream = (state_dir / ".instance.lock").open("a")
        try:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stream.close()
            raise ValueError("이 오버레이가 이미 실행 중입니다. 기존 창을 사용해주세요.") from None

    def close(self):
        self.stream.close()


class GlobalHotkey:
    def __init__(self, callback):
        self.callback, self.current = callback, None
        self.monitors = []
        self.binding = None

    def _matches(self, event):
        return self.binding is not None and not event.isARepeat() and self.binding == (
            int(event.modifierFlags()) & MODIFIER_MASK, int(event.keyCode()))

    def _global(self, event):
        if self._matches(event):
            self.callback()

    def _local(self, event):
        self._global(event)
        return event  # Shortcut recording in the focused entry must still receive it.

    def replace(self, name):
        try:
            name, modifiers, key = parse_hotkey(name)
        except ValueError as exc:
            return False, str(exc)
        from AppKit import NSEvent, NSEventMaskKeyDown
        from HIServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        if not AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
            return False, "시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용에서 tiki를 허용한 뒤 설정을 다시 적용해주세요. 생성 버튼은 바로 사용할 수 있습니다."
        if not self.monitors:
            global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, self._global)
            local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, self._local)
            new = [monitor for monitor in (global_monitor, local_monitor) if monitor is not None]
            if len(new) != 2:
                for monitor in new:
                    NSEvent.removeMonitor_(monitor)
                return False, "전역 단축키를 등록하지 못했습니다. 권한을 확인해주세요."
            self.monitors = new
        self.current, self.binding = name, (modifiers, key)
        return True, ""

    def close(self):
        if self.monitors:
            from AppKit import NSEvent
            for monitor in self.monitors:
                NSEvent.removeMonitor_(monitor)
        self.monitors = []
        self.binding, self.current = None, None
