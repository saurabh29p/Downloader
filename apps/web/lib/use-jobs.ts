"use client";

import type { Job } from "@anyget/shared";
import { useQuery } from "@tanstack/react-query";

import { listJobs } from "@/lib/api";
import { mergeJobs } from "@/lib/jobs";

export const JOBS_KEY = ["jobs"] as const;

/** All jobs, newest first. Kept live by <JobEventsBridge>. */
export function useJobs() {
  return useQuery<Job[]>({
    queryKey: JOBS_KEY,
    queryFn: listJobs,
    staleTime: 60_000,
    structuralSharing: (old, fresh) => mergeJobs(old as Job[] | undefined, fresh as Job[]),
  });
}
