export const DEMO_VIDEOS = [
  {
    id: "demo-01",
    title: "동영상 1",
    src: "/assets/demo-videos/demo-01.mp4",
    poster: "/assets/demo-videos/demo-01.jpg",
  },
  {
    id: "demo-02",
    title: "동영상 2",
    src: "/assets/demo-videos/demo-02.mp4",
    poster: "/assets/demo-videos/demo-02.jpg",
  },
  {
    id: "demo-03",
    title: "동영상 3",
    src: "/assets/demo-videos/demo-03.mp4",
    poster: "/assets/demo-videos/demo-03.jpg",
  },
];

export function captureVideoFrame(video: HTMLVideoElement): string {
  if (video.readyState < 2 || video.seeking || !video.videoWidth || !video.videoHeight) {
    throw new Error("영상이 준비된 뒤 다시 눌러주세요.");
  }
  const scale = Math.min(1, 960 / Math.max(video.videoWidth, video.videoHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("영상 장면을 읽지 못했습니다. 새로고침해주세요.");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const jpeg = canvas.toDataURL("image/jpeg", 0.78).split(",")[1];
  if (!jpeg || jpeg.length > 700000) throw new Error("영상 장면이 너무 큽니다. 다른 장면에서 다시 눌러주세요.");
  return jpeg;
}
