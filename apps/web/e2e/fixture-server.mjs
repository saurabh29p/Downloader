// Local file server for end-to-end tests. Serves deterministic files with
// Range support and Content-MD5, plus an HTML page and a slow mode.
//   GET/HEAD /files/<name>?size=<bytes>&slow=1
//   GET/HEAD /page.html?id=<tag> (links to report-<tag>.pdf and data-<tag>.zip)
import { createHash } from "node:crypto";
import { createServer } from "node:http";

const port = Number(process.env.FIXTURE_PORT ?? 8200);
const cache = new Map();

function fileFor(name, size) {
  const key = `${name}:${size}`;
  if (!cache.has(key)) {
    const seed = createHash("sha256").update(name).digest();
    const data = Buffer.alloc(size);
    for (let i = 0; i < size; i++) data[i] = seed[i % seed.length] ^ (i & 0xff);
    const md5 = createHash("md5").update(data).digest("base64");
    cache.set(key, { data, md5 });
  }
  return cache.get(key);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://127.0.0.1:${port}`);
  if (url.pathname === "/health") return res.end("ok");
  if (url.pathname === "/page.html") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    const tag = encodeURIComponent(url.searchParams.get("id") ?? "x");
    const body =
      "<!doctype html><title>A page</title>" +
      `<a href="/files/report-${tag}.pdf?size=40000">Report</a> ` +
      `<a href="/files/data-${tag}.zip?size=20000">Data</a>`;
    return res.end(req.method === "HEAD" ? undefined : body);
  }
  if (!url.pathname.startsWith("/files/")) {
    res.writeHead(404);
    return res.end();
  }

  const name = decodeURIComponent(url.pathname.slice("/files/".length));
  const size = Math.min(Number(url.searchParams.get("size") ?? 2 * 1024 * 1024), 64 * 1024 * 1024);
  const slow = url.searchParams.has("slow");
  const { data, md5 } = fileFor(name, size);

  let start = 0;
  let status = 200;
  const headers = {
    "Content-Type": "application/octet-stream",
    "Accept-Ranges": "bytes",
    "Content-MD5": md5,
  };
  const range = /^bytes=(\d+)-$/.exec(req.headers.range ?? "");
  if (range) {
    start = Number(range[1]);
    if (start >= size) {
      res.writeHead(416, { "Content-Range": `bytes */${size}` });
      return res.end();
    }
    status = 206;
    headers["Content-Range"] = `bytes ${start}-${size - 1}/${size}`;
  }
  headers["Content-Length"] = String(size - start);
  res.writeHead(status, headers);
  if (req.method === "HEAD") return res.end();

  const body = data.subarray(start);
  if (!slow) return res.end(body);
  const chunk = 64 * 1024;
  for (let offset = 0; offset < body.length && !res.destroyed; offset += chunk) {
    res.write(body.subarray(offset, offset + chunk));
    await sleep(120);
  }
  res.end();
}).listen(port, "127.0.0.1", () => console.log(`fixture server on ${port}`));
