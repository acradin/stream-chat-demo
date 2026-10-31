import type { RefObject } from "react";
import { DEMO_VIDEOS } from "@/lib/demoVideos";

interface Props {
  selectedId: string;
  onSelect: (id: string) => void;
  videoRef: RefObject<HTMLVideoElement>;
  onReady: (ready: boolean) => void;
  onSeek: () => void;
  error: string | null;
  onError: (message: string) => void;
}

export function DemoVideoPanel({ selectedId, onSelect, videoRef, onReady, onSeek, error, onError }: Props) {
  const selected = DEMO_VIDEOS.find(video => video.id === selectedId) ?? DEMO_VIDEOS[0];
  return (
    <section aria-label="사전 영상 체험" className="rounded-window bg-window p-5 shadow-window">
      <h1 className="text-xl font-bold text-ink">영상으로 채팅 체험하기</h1>
      <p className="mb-4 mt-2 text-sm leading-relaxed text-ink-faint">
        영상을 재생하고 원하는 장면에서 채팅 생성 버튼을 눌러보세요.
      </p>
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="체험 영상 선택">
        {DEMO_VIDEOS.map(video => (
          <button key={video.id} type="button" aria-pressed={video.id === selectedId}
            onClick={() => onSelect(video.id)}
            className={`rounded-xl border px-3 py-2 text-sm ${video.id === selectedId ? "border-brand bg-brand/10 text-brand" : "border-line-soft text-ink-soft"}`}>
            {video.title}
          </button>
        ))}
      </div>
      <video key={selected.id} ref={videoRef} src={selected.src} poster={selected.poster}
        controls playsInline muted preload="auto" aria-label={selected.title}
        className="aspect-video w-full rounded-xl bg-black"
        onLoadedData={() => onReady(true)} onCanPlay={() => onReady(true)}
        onSeeking={() => { onReady(false); onSeek(); }} onSeeked={() => onReady(true)}
        onError={() => { onReady(false); onError("영상을 재생하지 못했습니다. 새로고침하거나 다른 영상을 선택해주세요."); }} />
      <p className="mt-3 text-xs leading-relaxed text-ink-faint">
        생성 버튼을 누르면 영상이 멈추고 그 장면에 반응합니다. 음성은 분석하지 않습니다.
      </p>
      {error && <p role="alert" className="mt-3 text-sm text-status-error">{error}</p>}
    </section>
  );
}
