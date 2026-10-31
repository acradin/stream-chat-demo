import { useSessionStore } from "@/store/sessionStore";
import { charCount, formatCount } from "@/lib/format";

const MAX = 1000;

export function ContextInput() {
  const value = useSessionStore((s) => s.channelContext);
  const setValue = useSessionStore((s) => s.setChannelContext);
  const disabled = !useSessionStore((s) => s.config);

  const count = charCount(value);

  return (
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between">
        <label
          htmlFor="channel-context"
          className="text-[12px] font-semibold text-ink-soft"
        >
          방송 정보 <span className="font-normal text-ink-faint">· 선택</span>
        </label>
        <span className="font-mono text-[11px] tabular-nums text-ink-faint">
          {formatCount(count)} / {formatCount(MAX)}
        </span>
      </div>
      <textarea
        id="channel-context"
        value={value}
        disabled={disabled}
        maxLength={MAX}
        rows={4}
        onChange={(e) => setValue(e.target.value)}
        placeholder="예: 닉네임은 감자. 오늘은 처음 해보는 공포 게임 방송. 편하게 수다 떠는 분위기이고, 시청자 애칭은 감자단이에요."
        className="w-full resize-y rounded-xl border border-line bg-base-850 px-3.5 py-3 text-[14px] leading-relaxed text-ink placeholder:text-ink-faint/70 transition focus:border-brand/50 focus:bg-base-800 disabled:opacity-50"
      />
      <p className="mt-2 text-[11px] leading-relaxed text-ink-faint">
        주제·닉네임·진행 상황·배경을 적어두면 다음 버튼에도 재사용돼요. 비워두면
        페르소나 성격에 맞는 일반적인 한 줄을 만듭니다. 입력 내용은 이 컴퓨터의
        실험 로그에도 저장됩니다.
      </p>
    </div>
  );
}
