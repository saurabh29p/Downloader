import type { Job } from "@anyget/shared";

export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    url: "https://files.example.com/report.pdf",
    handler: "http",
    state: "downloading",
    title: "report.pdf",
    filename: "report.pdf",
    rel_path: null,
    downloaded: 512 * 1024,
    total: 1024 * 1024,
    speed: 256 * 1024,
    error: null,
    error_code: null,
    checksum_ok: null,
    connect: null,
    connect_label: null,
    options: {},
    created_at: "2026-11-04T10:00:00Z",
    updated_at: "2026-11-04T10:00:01Z",
    finished_at: null,
    ...overrides,
  } as Job;
}
