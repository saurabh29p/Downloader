import hashlib
import time
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.core.settings import Settings
from anyget.main import create_app

DATA = b"hello anyget " * 1000
URL = "https://files.test/hello.txt"


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with respx.mock(assert_all_called=False) as mock:
        mock.head(URL).mock(
            return_value=httpx.Response(
                200,
                headers={
                    "Content-Length": str(len(DATA)),
                    "Content-Type": "text/plain",
                    "Accept-Ranges": "bytes",
                },
            )
        )
        mock.get(URL).mock(return_value=httpx.Response(200, content=DATA))
        mock.head("https://files.test/page").mock(
            return_value=httpx.Response(200, headers={"Content-Type": "text/html"})
        )
        mock.get("https://files.test/page").mock(
            return_value=httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                text='<title>Reports</title><a href="/docs/annual.pdf">PDF</a>',
            )
        )
        with TestClient(create_app(settings)) as test_client:
            yield test_client


def wait_state(client: TestClient, job_id: str, state: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job: dict[str, object] = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] == state:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job never reached {state}: {job}")


def test_probe(client: TestClient) -> None:
    response = client.post("/api/probe", json={"url": "files.test/hello.txt?utm_source=x"})
    assert response.status_code == 200
    body = response.json()
    assert body["normalized_url"] == URL
    assert body["handler"] == "http"
    assert body["size"] == len(DATA)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd"],
)
def test_probe_blocked(client: TestClient, url: str) -> None:
    response = client.post("/api/probe", json={"url": url})
    assert response.status_code == 400
    assert response.json()["code"] == "blocked_url"


def test_unreachable_site_is_a_network_error(client: TestClient) -> None:
    # A site that resets the connection used to escape as a 500 "Internal Server Error".
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="down.test").mock(side_effect=httpx.ConnectError("connection reset"))
        response = client.post("/api/probe", json={"url": "https://down.test/file.bin"})
    assert response.status_code == 502
    assert response.json() == {"code": "network", "message": "network error: connection reset"}


def test_probe_web_page_lists_links(client: TestClient) -> None:
    response = client.post("/api/probe", json={"url": "https://files.test/page"})
    assert response.status_code == 200
    body = response.json()
    assert body["extra"]["kind"] == "webpage" and body["title"] == "Reports"
    assert [c["id"] for c in body["choices"]] == ["page", "https://files.test/docs/annual.pdf"]


def test_create_download_and_fetch_file(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"urls": [URL, "http://10.0.0.1/x", URL, " "]})
    assert response.status_code == 201
    body = response.json()
    assert len(body["jobs"]) == 1  # duplicate and blank skipped
    assert body["rejected"][0]["code"] == "blocked_url"

    job_id = body["jobs"][0]["id"]
    job = wait_state(client, job_id, "done")
    assert job["filename"] == "hello.txt"
    assert job["downloaded"] == len(DATA)

    file_response = client.get(f"/api/jobs/{job_id}/file")
    assert file_response.status_code == 200
    assert hashlib.sha256(file_response.content).digest() == hashlib.sha256(DATA).digest()
    assert "hello.txt" in file_response.headers["content-disposition"]

    listed = client.get("/api/jobs", params={"state": "done"}).json()
    assert [j["id"] for j in listed] == [job_id]

    assert client.post(f"/api/jobs/{job_id}/pause").status_code == 409
    assert client.delete(f"/api/jobs/{job_id}", params={"delete_file": True}).status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_unknown_job(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/jobs/nope"),
        ("POST", "/api/jobs/nope/pause"),
        ("POST", "/api/jobs/nope/resume"),
        ("DELETE", "/api/jobs/nope"),
        ("GET", "/api/jobs/nope/file"),
    ]:
        response = client.request(method, path)
        assert response.status_code == 404, path
        assert response.json()["code"] == "not_found"


def test_file_not_ready(client: TestClient, settings: Settings) -> None:
    from anyget.core.db import Database
    from anyget.core.jobs import JobState, JobStore

    store = JobStore(Database(settings))
    job = store.create(URL)
    store.update(job.id, state=JobState.paused, rel_path="../../etc/passwd")
    assert client.get(f"/api/jobs/{job.id}/file").status_code == 404
    store.update(job.id, state=JobState.done)
    assert client.get(f"/api/jobs/{job.id}/file").status_code == 404  # traversal refused


def test_create_validation(client: TestClient) -> None:
    assert client.post("/api/jobs", json={"urls": []}).status_code == 422


def test_timestamps_are_utc(client: TestClient) -> None:
    job_id = client.post("/api/jobs", json={"urls": [URL]}).json()["jobs"][0]["id"]
    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["created_at"].endswith(("Z", "+00:00"))
