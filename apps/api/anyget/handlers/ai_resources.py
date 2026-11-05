"""AI resources: Hugging Face models/datasets/spaces, Civitai models, Kaggle datasets.

Uses the sites' public JSON APIs to list files (with sizes and sha256 where given),
then downloads the chosen files through Net. Gated or private repos ask for your
own token (ANYGET_HF_TOKEN / ANYGET_CIVITAI_TOKEN / Kaggle key); we never bypass.
"""

import base64
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from anyget.core.filenames import safe_join, sanitize_filename
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    ProgressCallback,
)
from anyget.handlers.http_generic import HttpGenericHandler
from anyget.handlers.multi import RemoteFile, download_many

HF_HOSTS = {"huggingface.co", "www.huggingface.co", "hf.co"}
# Default selection: everything if the repo is small; otherwise the light files only.
SMALL_REPO = 5 * 1024**3
LIGHT_EXTS = (".md", ".json", ".txt", ".yaml", ".yml", ".py", ".model", ".tiktoken")


def _hf_target(url: str) -> tuple[str, str, str, str]:
    """→ (kind, repo, revision, path). kind is model, dataset or space."""
    seg = [unquote(s) for s in urlsplit(url).path.split("/") if s]
    kind = "model"
    if seg and seg[0] in ("datasets", "spaces"):
        kind, seg = seg[0][:-1], seg[1:]
    if len(seg) < 2:
        raise HandlerError("unsupported", "not a Hugging Face repository link")
    repo = f"{seg[0]}/{seg[1]}"
    rest = seg[2:]
    if len(rest) >= 2 and rest[0] in ("tree", "blob", "resolve"):
        return kind, repo, rest[1], "/".join(rest[2:])
    return kind, repo, "main", ""


class AiResourcesHandler:
    name = "ai_resources"

    def __init__(self, net: Net, settings: Settings) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)
        self.settings = settings

    def can_handle(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host in HF_HOSTS:
            return len([s for s in parts.path.split("/") if s]) >= 2
        if host in ("civitai.com", "www.civitai.com"):
            return parts.path.startswith("/models/")
        if host in ("www.kaggle.com", "kaggle.com"):
            return parts.path.startswith("/datasets/")
        return False

    # ----- sources ---------------------------------------------------------

    def _hf_headers(self) -> dict[str, str]:
        return (
            {"Authorization": f"Bearer {self.settings.hf_token}"} if self.settings.hf_token else {}
        )

    async def _hf(self, url: str) -> tuple[str, list[RemoteFile], str]:
        kind, repo, revision, path = _hf_target(url)
        api = f"https://huggingface.co/api/{kind}s/{repo}/tree/{quote(revision)}?recursive=true"
        response = await self.net.request("GET", api, headers=self._hf_headers() or None)
        if response.status_code in (401, 403):
            raise HandlerError(
                "login_required",
                "this Hugging Face repo is gated or private: "
                "accept its terms and add ANYGET_HF_TOKEN",
            )
        if response.status_code == 404:
            raise HandlerError("not_found", "Hugging Face has no repository like this")
        if response.status_code >= 400:
            raise HandlerError("upstream", f"Hugging Face answered {response.status_code}")
        prefix = "" if kind == "model" else f"{kind}s/"
        files = []
        for node in response.json():
            if node.get("type") != "file":
                continue
            rel = str(node["path"])
            if path and rel != path and not rel.startswith(path.rstrip("/") + "/"):
                continue
            lfs = node.get("lfs") or {}
            files.append(
                RemoteFile(
                    url=f"https://huggingface.co/{prefix}{repo}/resolve/{quote(revision)}/{quote(rel)}",
                    name=rel,
                    size=lfs.get("size") or node.get("size"),
                    sha256=lfs.get("oid") if lfs else None,
                    headers=self._hf_headers(),
                )
            )
        return repo, files, kind

    async def _civitai(self, url: str) -> tuple[str, list[RemoteFile], str]:
        seg = [s for s in urlsplit(url).path.split("/") if s]
        if len(seg) < 2 or not seg[1].isdigit():
            raise HandlerError("unsupported", "not a Civitai model link")
        response = await self.net.request("GET", f"https://civitai.com/api/v1/models/{seg[1]}")
        if response.status_code == 404:
            raise HandlerError("not_found", "Civitai has no model like this")
        if response.status_code >= 400:
            raise HandlerError("upstream", f"Civitai answered {response.status_code}")
        model = response.json()
        versions = model.get("modelVersions") or []
        if not versions:
            raise HandlerError("unavailable", "this model has no downloadable versions")
        token = self.settings.civitai_token
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        files = [
            RemoteFile(
                url=str(f["downloadUrl"]),
                name=f"{versions[0].get('name', 'v')}/{f['name']}",
                size=int(float(f.get("sizeKB") or 0) * 1024) or None,
                sha256=str((f.get("hashes") or {}).get("SHA256", "")).lower() or None,
                headers=headers,
            )
            for f in versions[0].get("files") or []
            if f.get("downloadUrl")
        ]
        return str(model.get("name") or f"civitai-{seg[1]}"), files, "civitai"

    async def _kaggle(self, url: str) -> tuple[str, list[RemoteFile], str]:
        seg = [s for s in urlsplit(url).path.split("/") if s]
        if len(seg) < 3:
            raise HandlerError("unsupported", "not a Kaggle dataset link")
        owner, slug = seg[1], seg[2]
        if not (self.settings.kaggle_username and self.settings.kaggle_key):
            raise HandlerError(
                "login_required",
                "Kaggle needs your own API key: set ANYGET_KAGGLE_USERNAME and ANYGET_KAGGLE_KEY",
            )
        auth = base64.b64encode(
            f"{self.settings.kaggle_username}:{self.settings.kaggle_key}".encode()
        ).decode()
        url = f"https://www.kaggle.com/api/v1/datasets/download/{quote(owner)}/{quote(slug)}"
        files = [
            RemoteFile(url=url, name=f"{slug}.zip", headers={"Authorization": f"Basic {auth}"})
        ]
        return f"{owner}/{slug}", files, "kaggle"

    async def _files(self, url: str) -> tuple[str, list[RemoteFile], str]:
        host = (urlsplit(url).hostname or "").lower()
        if host in HF_HOSTS:
            return await self._hf(url)
        if "civitai" in host:
            return await self._civitai(url)
        return await self._kaggle(url)

    # ----- contract --------------------------------------------------------

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        title, files, source = await self._files(url)
        if not files:
            raise HandlerError("not_found", "no files to download here")
        total = sum(f.size or 0 for f in files)
        small = total <= SMALL_REPO

        def default(f: RemoteFile) -> bool:
            return small or f.name.lower().endswith(LIGHT_EXTS)

        return Probe(
            url=url,
            handler=self.name,
            title=title,
            size=total or None,
            choices=[
                Choice(id=f.name, label=f.name, kind="file", size=f.size, default=default(f))
                for f in files
            ],
            extra={"kind": f"ai_{source}", "source": source, "files": len(files)},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        title, files, _source = await self._files(job.url)
        wanted = options.get("files")
        if isinstance(wanted, list) and wanted:
            names = {str(w) for w in wanted}
            files = [f for f in files if f.name in names]
        else:
            probe = options.get("probe") or {}
            defaults = {c["id"] for c in probe.get("choices", []) if c.get("default")}
            if defaults:
                files = [f for f in files if f.name in defaults]
        if not files:
            raise HandlerError("not_found", "none of the chosen files are here")
        folder = safe_join(job.output_dir, sanitize_filename(title.replace("/", " - ")))
        folder.mkdir(parents=True, exist_ok=True)
        return await download_many(self.http, job, files, folder, progress_cb)
