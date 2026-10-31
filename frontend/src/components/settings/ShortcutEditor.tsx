import { useState } from "react";
import { useUiStore } from "@/store/uiStore";

// 브라우저 포커스 상태에서 감지 가능한 키만 지원. OS 전역 단축키는
// 데스크톱 런타임 연동 후 지원(현재 미지원).
function describe(e: KeyboardEvent): string | null {
  const parts: string[] = [];
  if (e.ctrlKey) parts.push("Ctrl");
  if (e.altKey) parts.push("Alt");
  if (e.shiftKey) parts.push("Shift");
  if (e.metaKey) parts.push("Meta");
  const code = e.code;
  if (/^(Control|Alt|Shift|Meta)(Left|Right)$/.test(code)) return null;
  if (code === "CapsLock") return "Caps Lock";
  const label = code.replace(/^Key/, "").replace(/^Digit/, "");
  parts.push(label);
  return parts.join(" + ");
}

export function ShortcutEditor() {
  const hotkey = useUiStore((s) => s.hotkey);
  const setHotkey = useUiStore((s) => s.setHotkey);
  const [capturing, setCapturing] = useState(false);

  const display = hotkey === "Space" ? "Caps Lock" : hotkey;

  function onKeyDown(e: React.KeyboardEvent) {
    if (!capturing) return;
    e.preventDefault();
    const desc = describe(e.nativeEvent);
    if (desc) {
      setHotkey(desc);
      setCapturing(false);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <div
          tabIndex={capturing ? 0 : -1}
          onKeyDown={onKeyDown}
          className="flex h-12 flex-1 items-center justify-center rounded-xl text-[15px] font-semibold text-ink outline-none"
          style={{ background: "#686868" }}
        >
          {capturing ? "키를 눌러주세요…" : `⇧ ${display}`}
        </div>
        <button
          type="button"
          onClick={() => setCapturing((c) => !c)}
          className="h-12 rounded-xl px-6 text-[14px] font-semibold text-ink transition hover:brightness-110"
          style={{ background: "#484848" }}
        >
          {capturing ? "취소" : "변경"}
        </button>
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-ink-faint">
        이 창에 포커스가 있을 때 동작하는 브라우저 단축키입니다. OS 전역
        단축키는 데스크톱 앱에서 지원됩니다(현재 미지원).
      </p>
    </div>
  );
}
