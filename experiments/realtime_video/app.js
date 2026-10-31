"use strict";
const el = id => document.getElementById(id);
let config, stream, socket, timer, clock, running = false, encoding = false, sequence = 0, started = 0, generation = 0;
const canvas = document.createElement("canvas");
const context2d = canvas.getContext("2d");

function stop(message = "중지했습니다.") {
  generation += 1;
  running = false;
  clearTimeout(timer); clearInterval(clock);
  if (socket) {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "stop"}));
    socket.close(); socket = null;
  }
  if (stream) { stream.getTracks().forEach(track => track.stop()); stream = null; }
  el("preview").srcObject = null;
  el("start").disabled = !config; el("stop").disabled = true;
  for (const id of ["persona", "interval", "duration", "context"]) el(id).disabled = false;
  el("status").textContent = message;
}

async function sendFrame(run) {
  if (!running || run !== generation) return;
  const video = el("preview");
  const connection = socket;
  if (!encoding && video.videoWidth && connection?.readyState === WebSocket.OPEN && connection.bufferedAmount < 700000) {
    encoding = true;
    try {
      const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.max(1, Math.floor(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.floor(video.videoHeight * scale));
      context2d.drawImage(video, 0, 0, canvas.width, canvas.height);
      const jpeg = canvas.toDataURL("image/jpeg", .72).split(",")[1];
      if (jpeg.length > 700000) throw new Error("화면이 너무 복잡합니다. 더 작은 방송 창을 선택해주세요.");
      if (running && run === generation) connection.send(JSON.stringify({type: "frame", sequence: ++sequence, jpeg}));
    } catch { stop("화면을 전송하지 못했습니다. 공유 창을 다시 선택해주세요."); }
    finally { encoding = false; }
  }
  if (running && run === generation) timer = setTimeout(() => sendFrame(run), 1000);
}

el("start").addEventListener("click", async () => {
  if (running || !config) return;
  running = true;
  const run = ++generation;
  el("start").disabled = true; el("stop").disabled = false;
  for (const id of ["persona", "interval", "duration", "context"]) el(id).disabled = true;
  el("status").textContent = "공유할 방송 화면을 선택하세요.";
  try {
    const selected = await navigator.mediaDevices.getDisplayMedia({video: {frameRate: 1}, audio: false, selfBrowserSurface: "exclude"});
    if (run !== generation) { selected.getTracks().forEach(track => track.stop()); return; }
    stream = selected;
    stream.getAudioTracks().forEach(track => { track.stop(); stream.removeTrack(track); });
    stream.getVideoTracks()[0].addEventListener("ended", () => { if (run === generation) stop("화면 공유가 종료됐습니다."); });
    el("preview").srcObject = stream;
    await el("preview").play();
    if (run !== generation) return;
    el("chats").replaceChildren(); el("count").textContent = "0개"; el("frames").textContent = "전송 0장";
    el("latency").textContent = "판단 시간 —"; el("decision").textContent = "연결 중…";
    sequence = 0;
    socket = new WebSocket(`ws://${location.host}/ws`);
    const connection = socket;
    connection.addEventListener("open", () => {
      if (run !== generation) { connection.close(); return; }
      connection.send(JSON.stringify({type: "start", token: config.token, persona: el("persona").value,
        context: el("context").value, interval: Number(el("interval").value), duration: Number(el("duration").value)}));
    });
    connection.addEventListener("message", event => {
      if (run !== generation) return;
      const message = JSON.parse(event.data);
      if (message.type === "ready") {
        started = performance.now(); el("status").textContent = "화면을 관찰하고 있습니다.";
        clock = setInterval(() => {
          const elapsed = Math.floor((performance.now() - started) / 1000);
          el("elapsed").textContent = `${elapsed}초`;
          if (elapsed >= Number(el("duration").value)) stop("설정한 실험 시간이 끝났습니다.");
        }, 500);
        sendFrame(run);
      } else if (message.type === "frame") el("frames").textContent = `전송 ${message.frames}장`;
      else if (message.type === "decision") {
        el("latency").textContent = `판단 시간 ${(message.generation_ms / 1000).toFixed(2)}초`;
        el("count").textContent = `${message.chats}개`;
        el("decision").textContent = ({chat: "새로운 반응", wait: "반응할 장면을 기다립니다.", stale: "늦게 도착한 반응을 건너뛰었습니다.", cooldown: "채팅 간격을 기다립니다.", duplicate: "같은 채팅의 반복을 건너뛰었습니다."})[message.result];
        if (message.result === "chat") {
          const item = document.createElement("li"), label = document.createElement("b");
          label.textContent = `AI · ${el("persona").selectedOptions[0].textContent}`;
          item.append(label, document.createTextNode(message.comment)); el("chats").append(item);
          item.scrollIntoView({block: "nearest"});
        }
      } else if (message.type === "error" || message.type === "stopped") stop(message.message);
    });
    connection.addEventListener("error", () => { if (run === generation) stop("연결하지 못했습니다. 실험 서버를 확인해주세요."); });
    connection.addEventListener("close", () => { if (run === generation) stop("실험 연결이 종료됐습니다."); });
  } catch { if (run === generation) stop("화면 공유를 시작하지 못했습니다. Chrome 또는 Edge에서 다시 선택해주세요."); }
});
el("stop").addEventListener("click", () => stop());
window.addEventListener("pagehide", () => stop());
fetch("/config").then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(value => {
  config = value;
  for (const persona of config.personas) el("persona").add(new Option(persona.name, persona.id));
  el("mode").textContent = config.provider === "mock" ? "MOCK · 화면 연결과 표시만 확인합니다. AI 호출과 화면 해석은 하지 않습니다." : "실제 AI 실험 · 시작하면 선택한 화면이 OpenAI로 전송되며 API 사용량이 발생합니다.";
  el("start").disabled = false; el("status").textContent = "화면을 선택하면 시작합니다.";
}).catch(() => { el("status").textContent = "실험 서버 설정을 불러오지 못했습니다."; });
