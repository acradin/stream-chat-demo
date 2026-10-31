import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer as createTcpServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { createServer, preview } from "vite";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const webRoot = fileURLToPath(new URL("../", import.meta.url));
const repoRoot = path.resolve(webRoot, "../..");
const realFetch = globalThis.fetch;

async function availablePort() {
  const server = createTcpServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

test("web integration with the real local Mock API", { timeout: 30000 }, async (t) => {
  const temp = await mkdtemp(path.join(tmpdir(), "tiki-web-test-"));
  const backendPort = await availablePort();
  const backendUrl = `http://127.0.0.1:${backendPort}`;
  const venvPython = path.join(repoRoot, process.platform === "win32"
    ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : "python");
  const backend = spawn(python, ["-X", "utf8", "-B", "-m", "apps.web", "--provider", "mock",
    "--port", String(backendPort), "--output", path.join(temp, "run"),
    "--cooldown", "0", "--mock-delay", "0.03"], {
    cwd: repoRoot, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
  });
  let backendOutput = "";
  backend.stdout.on("data", (chunk) => { backendOutput += chunk; });
  backend.stderr.on("data", (chunk) => { backendOutput += chunk; });
  const oldTarget = process.env.API_TARGET;
  const oldDocument = globalThis.document;
  let vite;
  let previewServer;
  t.after(async () => {
    globalThis.fetch = realFetch;
    if (oldDocument === undefined) delete globalThis.document;
    else globalThis.document = oldDocument;
    if (oldTarget === undefined) delete process.env.API_TARGET;
    else process.env.API_TARGET = oldTarget;
    if (previewServer) await new Promise((resolve) => previewServer.httpServer.close(resolve));
    if (vite) await vite.close();
    if (backend.exitCode === null) {
      const stopped = once(backend, "exit");
      backend.kill();
      await stopped;
    }
    const resolvedTemp = path.resolve(temp);
    assert.ok(resolvedTemp.startsWith(path.resolve(tmpdir()) + path.sep));
    assert.ok(path.basename(resolvedTemp).startsWith("tiki-web-test-"));
    await rm(resolvedTemp, { recursive: true, force: true });
  });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (backend.exitCode !== null) throw new Error(backendOutput);
    try { ready = (await realFetch(`${backendUrl}/api/config`)).ok; } catch { /* starting */ }
    if (ready) break;
    await delay(50);
  }
  assert.ok(ready, `Mock backend failed to start: ${backendOutput}`);
  process.env.API_TARGET = backendUrl;
  vite = await createServer({ root: webRoot, configFile: path.join(webRoot, "vite.config.ts"),
    server: { port: await availablePort(), host: "127.0.0.1" }, optimizeDeps: { noDiscovery: true, include: [] }, logLevel: "error" });
  await vite.listen();
  const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
  const config = await (await realFetch(`${origin}/api/config`)).json();
  const payload = () => ({ client_request_id: crypto.randomUUID(), persona: "witty_friend",
    channel_context: "테스트 방송", clicked_video_s: null, video_session_id: null });

  await t.test("landing links to the existing React demo entry", async () => {
    const landing = await (await realFetch(origin)).text();
    assert.match(landing, /당신의 방송은<br\s*\/?>계속 티키타카/);
    assert.match(landing, /href="\/demo\/index\.html"/);
    assert.doesNotMatch(landing, /id="root"/);
    const demo = await (await realFetch(`${origin}/demo/index.html`)).text();
    assert.match(demo, /id="root"/);
    assert.match(demo, /src="\/src\/main\.tsx"/);
  });

  await t.test("proxy rejects foreign origins and missing tokens", async () => {
    for (const headers of [
      { Origin: "https://example.invalid", "X-Demo-Token": config.session_token },
      { Origin: origin },
    ]) {
      const response = await realFetch(`${origin}/api/trigger`, { method: "POST",
        headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(payload()) });
      assert.equal(response.status, 403);
    }
  });

  globalThis.document = { hidden: false };
  globalThis.fetch = (input, init = {}) => {
    const headers = new Headers(init.headers);
    if (init.method === "POST") headers.set("Origin", origin);
    return realFetch(new URL(input, origin), { ...init, headers });
  };
  const { useSessionStore } = await vite.ssrLoadModule("/src/store/sessionStore.ts");
  const records = async () => (await (await realFetch(`${origin}/api/export`)).text())
    .trim().split("\n").filter(Boolean).map((line) => JSON.parse(line));
  const context = () => ({ clickedAt: performance.now(), videoSessionId: null,
    clickedVideoS: null, contextVersion: useSessionStore.getState().contextVersion,
    readVideoTime: () => null });

  await t.test("default text-only generation is displayed and acknowledged", async () => {
    await useSessionStore.getState().loadConfig();
    assert.equal(useSessionStore.getState().connection, "ready");
    assert.equal(useSessionStore.getState().videoSessionId, null);
    await useSessionStore.getState().generate(context());
    const state = useSessionStore.getState();
    assert.equal(state.feedback.kind, "ready", state.feedback.message);
    assert.equal(state.messages.length, 1);
    assert.equal(state.displayedCount, 1);
    assert.match(state.messages[0].comment, /MOCK/);
    const logged = await records();
    assert.equal(logged.length, 1);
    assert.equal(logged[0].status, "displayed");
    assert.equal(logged[0].client_acknowledged, true);
    assert.equal(logged[0].clicked_video_s, null);
    const { MainScreen } = await vite.ssrLoadModule("/src/screens/MainScreen.tsx");
    // SSR uses Zustand's initial snapshot; client state is asserted above.
    // Check the screen exposes the result region and the actual default key.
    const markup = renderToStaticMarkup(React.createElement(MainScreen));
    assert.match(markup, /role="log"/);
    assert.match(markup, /Space/);
    assert.doesNotMatch(markup, /Caps Lock/);
  });

  await t.test("a changed context discards the response without displaying it", async () => {
    useSessionStore.getState().setPersona("warm_supporter");
    const stale = context();
    useSessionStore.getState().bumpContextVersion();
    await useSessionStore.getState().generate(stale);
    assert.equal(useSessionStore.getState().messages.length, 1);
    const logged = await records();
    assert.equal(logged.at(-1).status, "discarded");
    assert.equal(logged.at(-1).discard_reason, "video_context_changed");
  });

  await t.test("a video frame is generated, displayed and logged without image data", async () => {
    const frame = (await readFile(path.join(webRoot, "public/assets/demo-videos/demo-01.jpg"))).toString("base64");
    useSessionStore.getState().setVideo("sample", "sample-video");
    useSessionStore.getState().setPersona("analyst");
    const count = useSessionStore.getState().messages.length;
    assert.equal(useSessionStore.getState().config.supports_frames, true);
    await useSessionStore.getState().generate({ ...context(), videoSessionId: "sample-video",
      clickedVideoS: 2.5, readVideoTime: () => 2.5, frameJpeg: frame, demoVideoId: "demo-01" });
    assert.equal(useSessionStore.getState().messages.length, count + 1);
    const logged = (await records()).at(-1);
    assert.equal(logged.status, "displayed");
    assert.equal(logged.input_kind, "image");
    assert.equal(logged.demo_video_id, "demo-01");
    assert.equal(logged.clicked_video_s, 2.5);
    assert.equal(logged.displayed_video_s, 2.5);
    assert.ok(!JSON.stringify(logged).includes(frame));
    useSessionStore.getState().setVideo("none", null);
  });

  await t.test("built preview keeps the same POST proxy contract and all three videos", async () => {
    assert.ok(existsSync(path.join(webRoot, "dist/index.html")), "Run npm run build before npm test");
    previewServer = await preview({ root: webRoot, configFile: path.join(webRoot, "vite.config.ts"),
      preview: { port: await availablePort(), host: "127.0.0.1" }, logLevel: "error" });
    const previewOrigin = `http://127.0.0.1:${previewServer.httpServer.address().port}`;
    const landing = await (await realFetch(previewOrigin)).text();
    assert.match(landing, /href="\/demo\/index\.html"/);
    const demo = await (await realFetch(`${previewOrigin}/demo/index.html`)).text();
    assert.match(demo, /id="root"/);
    assert.match(demo, /src="\/assets\/demo-[^"]+\.js"/);
    assert.doesNotMatch(demo, /당신의 방송은<br\s*\/?>계속 티키타카/);
    const { DEMO_VIDEOS } = await vite.ssrLoadModule("/src/lib/demoVideos.ts");
    assert.equal(DEMO_VIDEOS.length, 3);
    assert.deepEqual(DEMO_VIDEOS.map(video => video.title), ["동영상 1", "동영상 2", "동영상 3"]);
    for (const video of DEMO_VIDEOS) {
      const clip = await realFetch(`${previewOrigin}${video.src}`, { headers: { Range: "bytes=0-31" } });
      assert.equal(clip.status, 206);
      assert.match(clip.headers.get("Content-Type"), /video\/mp4/);
      assert.equal((await clip.arrayBuffer()).byteLength, 32);
      const poster = await realFetch(`${previewOrigin}${video.poster}`);
      assert.equal(poster.status, 200);
      assert.match(poster.headers.get("Content-Type"), /image\/jpeg/);
    }
    const response = await realFetch(`${previewOrigin}/api/trigger`, { method: "POST",
      headers: { Origin: previewOrigin, "Content-Type": "application/json", "X-Demo-Token": config.session_token },
      body: JSON.stringify({ ...payload(), persona: "dry_comic" }) });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, "ready");
  });
});
