import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { build, manifestFor } from "../scripts/build.mjs";

describe("extension build", () => {
  it("writes valid MV3 manifests for Chrome and Firefox", () => {
    const chrome = manifestFor("chrome");
    const firefox = manifestFor("firefox");
    expect(chrome.manifest_version).toBe(3);
    expect(chrome.background.service_worker).toBe("background.js");
    expect(firefox.background.scripts).toEqual(["background.js"]);
    expect(firefox.browser_specific_settings.gecko.id).toMatch(/@/);
    for (const manifest of [chrome, firefox]) {
      expect(manifest.permissions).toEqual(["contextMenus", "storage"]);
      expect(manifest.host_permissions.every((p) => /127\.0\.0\.1|localhost/.test(p))).toBe(true);
    }
  });

  it("builds folders and zip files", () => {
    const out = build(mkdtempSync(join(tmpdir(), "anyget-ext-")));
    const manifest = JSON.parse(readFileSync(join(out, "chrome", "manifest.json"), "utf8"));
    expect(manifest.version).toMatch(/^\d+\.\d+\.\d+$/);
    const archive = readFileSync(join(out, `anyget-firefox-${manifest.version}.zip`));
    expect(archive.readUInt32LE(0)).toBe(0x04034b50); // local file header
    expect(archive.readUInt32LE(archive.length - 22)).toBe(0x06054b50); // end of central directory
    expect(archive.includes(Buffer.from("background.js"))).toBe(true);
  });
});
