// AnyGet extension: send the current page, a link, or a media file to your AnyGet.
import { DEFAULT_BASE, describeResult, jobsRequest, sendable } from "./lib.js";

const api = globalThis.browser ?? globalThis.chrome;

const MENUS = [
  { id: "anyget-link", title: "Download link with AnyGet", contexts: ["link"] },
  { id: "anyget-media", title: "Download with AnyGet", contexts: ["image", "video", "audio"] },
  { id: "anyget-page", title: "Download this page with AnyGet", contexts: ["page"] },
];

api.runtime.onInstalled.addListener(() => {
  api.contextMenus.removeAll(() => {
    for (const menu of MENUS) api.contextMenus.create(menu);
  });
});

async function settings() {
  const stored = await api.storage.sync.get({ base: DEFAULT_BASE, token: "" });
  return { base: stored.base || DEFAULT_BASE, token: stored.token || "" };
}

async function flash(ok, text) {
  await api.action.setBadgeBackgroundColor({ color: ok ? "#15803d" : "#b91c1c" });
  await api.action.setBadgeText({ text: ok ? "✓" : "!" });
  await api.action.setTitle({ title: `AnyGet: ${text}` });
  setTimeout(() => {
    api.action.setBadgeText({ text: "" });
    api.action.setTitle({ title: "Send this page to AnyGet" });
  }, 4000);
}

async function send(url) {
  if (!sendable(url)) {
    await flash(false, "only web links can be downloaded");
    return;
  }
  const { base, token } = await settings();
  const request = jobsRequest(base, token, [url]);
  try {
    const response = await fetch(request.url, request.init);
    const body = await response.json().catch(() => null);
    const result = describeResult(response.status, body);
    await flash(result.ok, result.text);
  } catch {
    await flash(false, `could not reach ${base} — is AnyGet running?`);
  }
}

api.contextMenus.onClicked.addListener((info, tab) => {
  const url =
    info.menuItemId === "anyget-link"
      ? info.linkUrl
      : info.menuItemId === "anyget-media"
        ? info.srcUrl
        : (info.pageUrl ?? tab?.url);
  void send(url);
});

api.action.onClicked.addListener((tab) => void send(tab.url));
