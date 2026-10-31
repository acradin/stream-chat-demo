import { useEffect, useRef, useState } from "react";
import { useUiStore } from "@/store/uiStore";
import { formatHotkey } from "@/lib/format";

// 브라우저 포커스 상태에서 감지 가능한 키만 지원. OS 전역 단축키는
// 데스크톱 런타임 연동 후 지원(현재 미지원).

// 단축키로 부적합하거나 브라우저/OS 와 자주 충돌하는 조합.
const BROWSER_CONFLICTS = new Set([
  "Ctrl + KeyW",
  "Ctrl + KeyT",
  "Ctrl + KeyN",
  "Ctrl + KeyR",
  "Ctrl + KeyL",
  "Ctrl + KeyD",
  "Ctrl + KeyP",
  "Ctrl + KeyS",
  "Ctrl + KeyF",
  "Meta + KeyW",
  "Meta + KeyT",
  "Meta + KeyN",
  "Meta + KeyR",
  "Meta + KeyQ",
]);

interface Parsed {
  label: string;
  conflict: string | null;
}

/**
 * 키 이벤트를 단축키 라벨로 변환. 부적합/충돌 시 안내 메시지를 함께 돌려준다.
 * - 수식키 단독(Shift/Ctrl/Alt/Meta)과 Tab 은 거부한다.
 * - CapsLock 은 허용하되 토글 키 특성을 안내한다.
 */
function describe(e: KeyboardEvent): Parsed | null {
  const code = e.code;

  // 수식키 단독 입력은 단축키로 사용할 수 없음 (Tab 과 동일하게 안내)
  const modifierName: Record<string, string> = {
    ShiftLeft: "Shift",
    ShiftRight: "Shift",
    ControlLeft: "Ctrl",
    ControlRight: "Ctrl",
    AltLeft: "Alt",
    AltRight: "Alt",
    MetaLeft: "Meta",
    MetaRight: "Meta",
  };
  if (code in modifierName) {
    return {
      label: "",
      conflict: `${modifierName[code]} 키는 단축키로 사용할 수 없어요.`,
    };
  }

  // Tab 은 포커스 이동이라 단축키로 허용하지 않음
  if (code === "Tab") {
    return { label: "", conflict: "Tab 키는 단축키로 사용할 수 없어요." };
  }

  // CapsLock: 단독 키로만 허용 (수식키 조합 의미 없음)
  if (code === "CapsLock") {
    return {
      label: "Caps Lock",
      conflict:
        "Caps Lock 은 토글 키라 일부 환경에서 반응이 일정하지 않을 수 있어요.",
    };
  }

  const mods: string[] = [];
  if (e.ctrlKey) mods.push("Ctrl");
  if (e.altKey) mods.push("Alt");
  if (e.shiftKey) mods.push("Shift");
  if (e.metaKey) mods.push("Meta");

  const keyLabel =
    code === "Space" ? "Space" : code.replace(/^Key/, "").replace(/^Digit/, "");
  const label = [...mods, keyLabel].join(" + ");

  const conflict = BROWSER_CONFLICTS.has([...mods, code].join(" + "))
    ? "브라우저 기본 단축키와 겹칠 수 있어요. 다른 조합을 권장해요."
    : null;

  return { label, conflict };
}

export function ShortcutEditor() {
  const hotkey = useUiStore((s) => s.hotkey);
  const setHotkey = useUiStore((s) => s.setHotkey);
  const [capturing, setCapturing] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // 캡처 시작 시 입력 박스에 포커스를 줘 keydown 을 확실히 수신.
  useEffect(() => {
    if (capturing) boxRef.current?.focus();
  }, [capturing]);

  // 메인 버튼과 동일한 공용 포매터로 표시 (단일 소스 + 통일된 규칙).
  const display = formatHotkey(hotkey);

  function onKeyDown(e: React.KeyboardEvent) {
    if (!capturing) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.key === "Escape") {
      setCapturing(false);
      return;
    }
    const parsed = describe(e.nativeEvent);
    if (!parsed) return; // 수식키 단독: 계속 대기

    if (!parsed.label) {
      // Tab 등 사용 불가 키: 안내만 하고 계속 캡처
      setWarning(parsed.conflict);
      return;
    }

    setHotkey(parsed.label);
    setWarning(parsed.conflict);
    setCapturing(false);
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <div
          ref={boxRef}
          data-hotkey-capture={capturing || undefined}
          aria-label="?? ??? ??"
          role="button"
          tabIndex={0}
          onKeyDown={onKeyDown}
          onBlur={() => setCapturing(false)}
          className="flex h-12 flex-1 items-center justify-center rounded-xl text-[15px] font-semibold text-ink outline-none ring-brand/60 focus:ring-2"
          style={{ background: "#686868" }}
        >
          {capturing ? "키를 눌러주세요…" : `⇧ ${display}`}
        </div>
        <button
          type="button"
          onClick={() => {
            setWarning(null);
            setCapturing((c) => !c);
          }}
          className="h-12 rounded-xl px-6 text-[14px] font-semibold text-ink transition hover:brightness-110"
          style={{ background: "#484848" }}
        >
          {capturing ? "취소" : "변경"}
        </button>
      </div>
      {warning ? (
        <p className="mt-2 text-[10px] leading-relaxed text-status-warn">
          {warning}
        </p>
      ) : (
        <p className="mt-2 text-[10px] leading-relaxed text-ink-faint">
          이 창에 포커스가 있을 때 동작하는 브라우저 단축키입니다. OS 전역
          단축키는 데스크톱 앱에서 지원됩니다(현재 미지원).
        </p>
      )}
    </div>
  );
}
