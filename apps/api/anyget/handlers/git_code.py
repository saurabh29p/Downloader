"""Code hosts: GitHub, GitLab, Codeberg (Forgejo/Gitea) and Bitbucket.

Repos come as a zip of the default branch (or a ref), single files via their raw
URL, folders via the GitHub tree API (other hosts: the repo zip), GitHub release
assets and gists. No `git` process is started: every byte goes through Net and
the SSRF guard. An optional GitHub token (ANYGET_GITHUB_TOKEN) lifts API limits.
"""

from dataclasses import dataclass
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

HOSTS = {
    "github.com": "github",
    "www.github.com": "github",
    "gist.github.com": "gist",
    "raw.githubusercontent.com": "github_raw",
    "gitlab.com": "gitlab",
    "codeberg.org": "codeberg",
    "bitbucket.org": "bitbucket",
}
MAX_TREE_FILES = 1000


@dataclass(frozen=True)
class Target:
    """What a code-host link points at."""

    host: str
    kind: str  # repo, file, folder, release, release_asset, gist
    owner: str = ""
    repo: str = ""
    ref: str = ""
    path: str = ""
    tag: str = ""
    gist_id: str = ""
    url: str = ""


def _segments(url: str) -> list[str]:
    return [unquote(s) for s in urlsplit(url).path.split("/") if s]


def parse_target(url: str) -> Target:
    parts = urlsplit(url)
    host = HOSTS.get((parts.hostname or "").lower())
    if host is None:
        raise HandlerError("unsupported", "not a supported code host")
    seg = _segments(url)
    if host == "gist":
        if not seg:
            raise HandlerError("unsupported", "not a gist link")
        return Target(host="gist", kind="gist", gist_id=seg[-1], url=url)
    if host == "github_raw":
        if len(seg) < 4:
            raise HandlerError("unsupported", "not a raw file link")
        return Target("github", "file", seg[0], seg[1], seg[2], "/".join(seg[3:]), url=url)
    if host == "gitlab":
        # gitlab.com/<group>/<sub>/<project>[/-/blob|tree|raw/<ref>/<path>]
        if "-" in seg:
            dash = seg.index("-")
            project, rest = seg[:dash], seg[dash + 1 :]
        else:
            project, rest = seg, []
        if len(project) < 2:
            raise HandlerError("unsupported", "not a GitLab project link")
        owner, repo = "/".join(project[:-1]), project[-1]
        if len(rest) >= 2 and rest[0] in ("blob", "raw"):
            return Target("gitlab", "file", owner, repo, rest[1], "/".join(rest[2:]), url=url)
        if len(rest) >= 2 and rest[0] == "tree":
            return Target("gitlab", "folder", owner, repo, rest[1], "/".join(rest[2:]), url=url)
        return Target("gitlab", "repo", owner, repo, url=url)
    if len(seg) < 2:
        raise HandlerError("unsupported", "not a repository link")
    owner, repo = seg[0], seg[1].removesuffix(".git")
    rest = seg[2:]
    if host == "github":
        if len(rest) >= 3 and rest[0] == "blob":
            return Target("github", "file", owner, repo, rest[1], "/".join(rest[2:]), url=url)
        if len(rest) >= 2 and rest[0] == "tree":
            return Target("github", "folder", owner, repo, rest[1], "/".join(rest[2:]), url=url)
        if len(rest) >= 4 and rest[:2] == ["releases", "download"]:
            return Target(
                "github",
                "release_asset",
                owner,
                repo,
                tag=rest[2],
                path="/".join(rest[3:]),
                url=url,
            )
        if len(rest) >= 3 and rest[:2] == ["releases", "tag"]:
            return Target("github", "release", owner, repo, tag=rest[2], url=url)
        if rest[:2] == ["releases", "latest"] or rest == ["releases"]:
            return Target("github", "release", owner, repo, tag="latest", url=url)
        return Target("github", "repo", owner, repo, url=url)
    if host == "codeberg":
        # /<o>/<r>/src/(branch|tag|commit)/<ref>/<path>
        if len(rest) >= 3 and rest[0] == "src":
            kind = "file" if "." in rest[-1] else "folder"
            return Target("codeberg", kind, owner, repo, rest[2], "/".join(rest[3:]), url=url)
        return Target("codeberg", "repo", owner, repo, url=url)
    # bitbucket: /<o>/<r>/src/<ref>/<path>
    if len(rest) >= 2 and rest[0] == "src":
        kind = "file" if len(rest) > 2 and "." in rest[-1] else "folder"
        return Target("bitbucket", kind, owner, repo, rest[1], "/".join(rest[2:]), url=url)
    return Target("bitbucket", "repo", owner, repo, url=url)


def raw_file_url(t: Target) -> str:
    path = quote(t.path)
    if t.host == "github":
        return f"https://raw.githubusercontent.com/{t.owner}/{t.repo}/{quote(t.ref)}/{path}"
    if t.host == "gitlab":
        return f"https://gitlab.com/{t.owner}/{t.repo}/-/raw/{quote(t.ref)}/{path}"
    if t.host == "codeberg":
        return f"https://codeberg.org/{t.owner}/{t.repo}/raw/branch/{quote(t.ref)}/{path}"
    return f"https://bitbucket.org/{t.owner}/{t.repo}/raw/{quote(t.ref)}/{path}"


def repo_zip_url(t: Target, ref: str = "HEAD") -> str:
    r = quote(ref)
    if t.host == "github":
        return f"https://github.com/{t.owner}/{t.repo}/archive/{r}.zip"
    if t.host == "gitlab":
        name = quote(t.repo)
        url = f"https://gitlab.com/{t.owner}/{t.repo}/-/archive/{r}/{name}-{r}.zip"
        return f"{url}?path={quote(t.path)}" if t.path else url
    if t.host == "codeberg":
        return f"https://codeberg.org/{t.owner}/{t.repo}/archive/{r}.zip"
    return f"https://bitbucket.org/{t.owner}/{t.repo}/get/{r}.zip"


class GitCodeHandler:
    name = "git_code"

    def __init__(self, net: Net, settings: Settings) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)
        self.token = settings.github_token

    def can_handle(self, url: str) -> bool:
        try:
            parse_target(url)
        except HandlerError:
            return False
        return True

    def _api_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _github(self, path: str) -> Any:
        response = await self.net.request(
            "GET", f"https://api.github.com{path}", headers=self._api_headers()
        )
        if response.status_code == 404:
            raise HandlerError("not_found", "GitHub says this does not exist (or it is private)")
        if response.status_code in (403, 429):
            raise HandlerError(
                "rate_limited",
                "GitHub's API limit was reached; try later or add ANYGET_GITHUB_TOKEN",
            )
        if response.status_code >= 400:
            raise HandlerError("upstream", f"GitHub answered {response.status_code}")
        return response.json()

    async def _codeberg_default_branch(self, t: Target) -> str:
        response = await self.net.request(
            "GET", f"https://codeberg.org/api/v1/repos/{t.owner}/{t.repo}"
        )
        if response.status_code >= 400:
            raise HandlerError("not_found", "Codeberg says this repository does not exist")
        return str(response.json().get("default_branch") or "main")

    async def _files(self, t: Target) -> tuple[str, list[RemoteFile]]:
        """Title and the files this link stands for."""
        label = f"{t.owner}/{t.repo}"
        if t.kind == "gist":
            gist = await self._github(f"/gists/{quote(t.gist_id)}")
            files = [
                RemoteFile(url=f["raw_url"], name=name, size=f.get("size"))
                for name, f in (gist.get("files") or {}).items()
            ]
            title = gist.get("description") or f"gist {t.gist_id}"
            return title, files
        if t.kind == "file":
            name = t.path.rsplit("/", 1)[-1] or t.repo
            return f"{label}: {t.path}", [RemoteFile(url=raw_file_url(t), name=name)]
        if t.kind == "release_asset":
            url = f"https://github.com/{t.owner}/{t.repo}/releases/download/{quote(t.tag)}/{quote(t.path)}"
            return f"{label} {t.tag}", [RemoteFile(url=url, name=t.path)]
        if t.kind == "release":
            path = "/releases/latest" if t.tag == "latest" else f"/releases/tags/{quote(t.tag)}"
            release = await self._github(f"/repos/{t.owner}/{t.repo}{path}")
            tag = str(release.get("tag_name") or t.tag)
            files = [
                RemoteFile(url=a["browser_download_url"], name=a["name"], size=a.get("size"))
                for a in release.get("assets") or []
            ]
            files.append(RemoteFile(url=repo_zip_url(t, tag), name=f"{t.repo}-{tag}-source.zip"))
            return f"{label} {release.get('name') or tag}", files
        if t.kind == "folder" and t.host == "github":
            tree = await self._github(
                f"/repos/{t.owner}/{t.repo}/git/trees/{quote(t.ref)}?recursive=1"
            )
            prefix = t.path.rstrip("/") + "/" if t.path else ""
            files = [
                RemoteFile(
                    url=raw_file_url(
                        Target("github", "file", t.owner, t.repo, t.ref, node["path"])
                    ),
                    name=node["path"][len(prefix) :],
                    size=node.get("size"),
                )
                for node in tree.get("tree") or []
                if node.get("type") == "blob" and node["path"].startswith(prefix)
            ][:MAX_TREE_FILES]
            if not files:
                raise HandlerError("not_found", "this folder is empty or does not exist")
            return f"{label}: {t.path or '/'}", files
        if t.kind == "folder" and t.host == "gitlab":
            return f"{label}: {t.path}", [
                RemoteFile(
                    url=repo_zip_url(t, t.ref), name=f"{t.repo}-{t.path.replace('/', '-')}.zip"
                )
            ]
        # Whole repository (or a folder on hosts without a tree API): zip of the ref.
        ref = t.ref or "HEAD"
        if t.host == "codeberg" and not t.ref:
            ref = await self._codeberg_default_branch(t)
        return label, [RemoteFile(url=repo_zip_url(t, ref), name=f"{t.repo}-{ref}.zip")]

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        t = parse_target(url)
        title, files = await self._files(t)
        if not files:
            raise HandlerError("not_found", "nothing to download here")
        return Probe(
            url=url,
            handler=self.name,
            title=title,
            size=sum(f.size or 0 for f in files) or None,
            choices=[
                Choice(id=f.name, label=f.name, kind="file", size=f.size, default=True)
                for f in files
            ],
            extra={"kind": f"code_{t.kind}", "host": t.host, "files": len(files)},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        t = parse_target(job.url)
        title, files = await self._files(t)
        wanted = options.get("files")
        if isinstance(wanted, list) and wanted:
            names = {str(w) for w in wanted}
            files = [f for f in files if f.name in names]
            if not files:
                raise HandlerError("not_found", "none of the chosen files are here")
        if len(files) == 1 and t.kind in ("file", "release_asset", "repo"):
            folder = job.output_dir
        else:
            folder = safe_join(job.output_dir, sanitize_filename(title, fallback=t.repo or "code"))
        folder.mkdir(parents=True, exist_ok=True)
        return await download_many(self.http, job, files, folder, progress_cb)
