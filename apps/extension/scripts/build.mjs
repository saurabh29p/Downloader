// Builds dist/chrome and dist/firefox plus a zip of each (store-only zip, no dependencies).
import {
  cpSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { version } = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const base = JSON.parse(readFileSync(join(root, "src", "manifest.base.json"), "utf8"));

export const TARGETS = {
  chrome: { background: { service_worker: "background.js", type: "module" } },
  firefox: {
    background: { scripts: ["background.js"], type: "module" },
    browser_specific_settings: {
      gecko: { id: "anyget@anyget.local", strict_min_version: "128.0" },
    },
  },
};

export function manifestFor(target) {
  return { ...base, version, ...TARGETS[target] };
}

const CRC = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
const crc32 = (buf) => {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

/** A zip with stored (uncompressed) entries: enough for browser stores and sideloading. */
export function zip(dir) {
  const locals = [];
  const centrals = [];
  let offset = 0;
  for (const path of files(dir).sort()) {
    const name = Buffer.from(relative(dir, path).split("\\").join("/"));
    const data = readFileSync(path);
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(name.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE(offset, 42);
    locals.push(local, name, data);
    centrals.push(central, name);
    offset += local.length + name.length + data.length;
  }
  const centralSize = centrals.reduce((n, b) => n + b.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(centrals.length / 2, 8);
  end.writeUInt16LE(centrals.length / 2, 10);
  end.writeUInt32LE(centralSize, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, ...centrals, end]);
}

export function build(out = join(root, "dist")) {
  rmSync(out, { recursive: true, force: true });
  for (const target of Object.keys(TARGETS)) {
    const dir = join(out, target);
    mkdirSync(dir, { recursive: true });
    for (const name of readdirSync(join(root, "src"))) {
      if (name !== "manifest.base.json") cpSync(join(root, "src", name), join(dir, name));
    }
    cpSync(join(root, "icons"), join(dir, "icons"), { recursive: true });
    writeFileSync(join(dir, "manifest.json"), `${JSON.stringify(manifestFor(target), null, 2)}\n`);
    writeFileSync(join(out, `anyget-${target}-${version}.zip`), zip(dir));
  }
  return out;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  console.log(`built ${relative(process.cwd(), build())}`);
}
