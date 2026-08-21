import { createServer } from "node:http";
import { execFile } from "node:child_process";
import { mkdir, readdir, stat } from "node:fs/promises";
import { promisify } from "node:util";
import crypto from "node:crypto";
import path from "node:path";

const execFileAsync = promisify(execFile);
const host = process.env.MUSIC_WORKER_HOST || "127.0.0.1";
const port = Number(process.env.MUSIC_WORKER_PORT || 8787);
const token = process.env.NODE_MUSIC_WORKER_TOKEN || "";
const cacheDir = path.resolve(process.env.AUDIO_CACHE_DIR || "/tmp/bot_audio_cache");
const locks = new Map();

function authorized(request) {
  return !token || request.headers.authorization === `Bearer ${token}`;
}

function send(response, status, payload) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}

async function requestBody(request) {
  let body = "";
  for await (const chunk of request) body += chunk;
  return JSON.parse(body || "{}");
}

async function findCachedFile(folder) {
  const entries = await readdir(folder, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const filePath = path.join(folder, entry.name);
    const details = await stat(filePath);
    if (details.size > 0) files.push({ filePath, modified: details.mtimeMs });
  }
  files.sort((left, right) => right.modified - left.modified);
  return files[0]?.filePath || null;
}

async function prefetch(query) {
  const { stdout: metadataJson } = await execFileAsync("yt-dlp", [
    "--dump-single-json", "--no-playlist", "--skip-download", query,
  ], { maxBuffer: 8 * 1024 * 1024, timeout: 60000 });
  const metadata = JSON.parse(metadataJson);
  const id = String(metadata.id || crypto.createHash("sha256").update(query).digest("hex").slice(0, 24));
  const folder = path.join(cacheDir, id.replace(/[^A-Za-z0-9_.-]/g, "_"));
  await mkdir(folder, { recursive: true });
  const cachedFile = await findCachedFile(folder);
  if (cachedFile) return { path: cachedFile, title: metadata.title, id };

  if (!locks.has(id)) {
    locks.set(id, (async () => {
      const args = ["--no-playlist", "--format", "bestaudio/best", "--output", path.join(folder, "audio.%(ext)s"), query];
      if (process.env.YTDL_COOKIE_FILE) args.unshift("--cookies", process.env.YTDL_COOKIE_FILE);
      await execFileAsync("yt-dlp", args, { maxBuffer: 2 * 1024 * 1024, timeout: 300000 });
    })().finally(() => locks.delete(id)));
  }
  await locks.get(id);
  const downloadedFile = await findCachedFile(folder);
  if (!downloadedFile) throw new Error("yt-dlp did not produce an audio file");
  return {
    path: downloadedFile,
    title: metadata.title,
    duration: metadata.duration,
    webpage_url: metadata.webpage_url,
    id,
  };
}

const server = createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") return send(response, 200, { ok: true });
  if (request.method !== "POST" || request.url !== "/prefetch") return send(response, 404, { error: "not found" });
  if (!authorized(request)) return send(response, 401, { error: "unauthorized" });
  try {
    const body = await requestBody(request);
    if (typeof body.query !== "string" || !body.query.trim()) return send(response, 400, { error: "query is required" });
    return send(response, 200, { ok: true, source: await prefetch(body.query.trim()) });
  } catch (error) {
    return send(response, 502, { ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

server.listen(port, host, () => console.log(`Music worker listening on http://${host}:${port}`));
