// Local file server for end-to-end tests. Serves deterministic files with
// Range support and Content-MD5, plus an HTML page and a slow mode.
//   GET/HEAD /files/<name>?size=<bytes>&slow=1
//   GET/HEAD /page.html?id=<tag> (links to report-<tag>.pdf and data-<tag>.zip)
//   GET /gutendex/books?search=<q> (Gutendex stand-in), /iiif/<tag>/manifest.json (IIIF v3)
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
  // A Gutendex stand-in: one public-domain book titled after the search words.
  if (url.pathname === "/gutendex/books") {
    const q = url.searchParams.get("search") ?? "book";
    const slug = q.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(
      JSON.stringify({
        count: 1,
        results: [
          {
            id: 7,
            title: q,
            authors: [{ name: "Fixture, Author" }],
            languages: ["en"],
            copyright: false,
            formats: {
              "application/epub+zip": `http://127.0.0.1:${port}/files/${slug}.epub?size=30000`,
              "text/plain; charset=utf-8": `http://127.0.0.1:${port}/files/${slug}.txt?size=9000`,
            },
          },
        ],
      }),
    );
  }
  // A IIIF Presentation 3 manifest with three pages (served as small files).
  const iiif = /^\/iiif\/([\w-]+)\/(manifest\.json|img\/(\d+)\/.*)$/.exec(url.pathname);
  if (iiif) {
    const [, tag, , page] = iiif;
    if (page) {
      const { data } = fileFor(`iiif-${tag}-${page}`, 5000);
      res.writeHead(200, { "Content-Type": "image/jpeg", "Content-Length": String(data.length) });
      return res.end(req.method === "HEAD" ? undefined : data);
    }
    const base = `http://127.0.0.1:${port}/iiif/${tag}`;
    const canvas = (n) => ({
      id: `${base}/canvas/${n}`,
      type: "Canvas",
      label: { none: [`Page ${n}`] },
      items: [
        {
          items: [
            {
              body: {
                id: `${base}/img/${n}/full/max/0/default.jpg`,
                type: "Image",
                format: "image/jpeg",
                service: [{ id: `${base}/img/${n}`, type: "ImageService3" }],
              },
            },
          ],
        },
      ],
    });
    res.writeHead(200, { "Content-Type": "application/ld+json" });
    return res.end(
      JSON.stringify({
        "@context": "http://iiif.io/api/presentation/3/context.json",
        type: "Manifest",
        label: { en: [`Album ${tag}`] },
        rights: "https://creativecommons.org/publicdomain/mark/1.0/",
        items: [1, 2, 3].map(canvas),
      }),
    );
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
