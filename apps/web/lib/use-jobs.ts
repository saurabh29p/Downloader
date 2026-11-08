"use client";

import type { Job } from "@anyget/shared";
import { useQuery } from "@tanstack/react-query";

import { listJobs } from "@/lib/api";
import { reconcile } from "@/lib/jobs-sync";

export const JOBS_KEY = ["jobs"] as const;

/**
 * All jobs, newest first. Kept live by <JobEventsBridge>. Each response is reconciled
 * with stream events that arrived while it was on its way (lib/jobs-sync.ts).
 */
export function useJobs() {
  return useQuery<Job[]>({
    queryKey: JOBS_KEY,
    queryFn: async ({ client }) => {
      const startedAt = Date.now();
      const fresh = await listJobs();
      return reconcile(client.getQueryData<Job[]>(JOBS_KEY), fresh, startedAt);
    },
    staleTime: 60_000,
  });
}
