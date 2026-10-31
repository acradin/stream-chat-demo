import { useRef } from "react";
import { Pencil } from "lucide-react";
import { useSessionStore } from "@/store/sessionStore";
import { charCount, formatCount } from "@/lib/format";

// 시안 기준 500자 표기. 백엔드 한도(1000)는 넘지 않는다.
const MAX = 500;

export function BroadcastDescription() {
  const value = useSessionStore((s) => s.channelContext);
  const setValue = useSessionStore((s) => s.setChannelContext);
  const disabled = !useSessionStore((s) => s.config);
  const ref = useRef<HTMLTextAreaElement>(null);

  const count = charCount(value);

  return (
    <div
      className="relative rounded-2xl p-4"
      style={{ background: "#3d3d3d" }}
    >
      <button
        type="button"
        onClick={() => ref.current?.focus()}
        className="absolute right-3 top-3 text-ink-soft transition hover:text-white"
        title="수정"
        aria-label="방송 설명 수정"
      >
        <Pencil className="h-4 w-4" />
      </button>
      <textarea
        ref={ref}
        value={value}
        disabled={disabled}
        maxLength={MAX}
        rows={3}
        onChange={(e) => setValue(e.target.value)}
        placeholder={
          "나는 롤을 주로 하는 스트리머야.\n티어는 플레티넘이고, 경쟁전 위주로 방송해.\n시청자와 편하게 소통하는 분위기를 좋아해."
        }
        className="w-full resize-none bg-transparent pr-6 text-[14px] leading-relaxed text-ink outline-none placeholder:text-ink-faint/60"
      />
      <div className="mt-1 text-right font-mono text-[11px] text-ink-faint">
        {formatCount(count)} / {formatCount(MAX)}자
      </div>
    </div>
  );
}
