"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { toast } from "@/lib/toast";

import { applyJobEvent, jobName, type JobEvent } from "@/lib/jobs";
import { JOBS_KEY } from "@/lib/use-jobs";
import type { Job } from "@anyget/shared";

type Connection = "connecting" | "live" | "reconnecting";
const ConnectionContext = createContext<Connection>("connecting");
export const useConnection = () => useContext(ConnectionContext);

/**
 * One EventSource for the whole app: server job events update the TanStack
 * Query cache, and finished/failed downloads are announced with a toast.
 */
export function JobEventsBridge({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const t = useTranslations("Jobs");
  const [connection, setConnection] = useState<Connection>("connecting");

  useEffect(() => {
    let source: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let closed = false;

    const handle = (type: JobEvent["type"]) => (message: MessageEvent<string>) => {
      const job = JSON.parse(message.data) as Job;
      const previous = queryClient.getQueryData<Job[]>(JOBS_KEY)?.find((j) => j.id === job.id);
      queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs) =>
        applyJobEvent(jobs, { type, job } as JobEvent),
      );
      if (type === "job.updated" && previous && previous.state !== job.state) {
        if (job.state === "done") toast.success(t("finished", { name: jobName(job) }));
        if (job.state === "failed") toast.error(t("failedToast", { name: jobName(job) }));
      }
    };

    const connect = () => {
      source = new EventSource("/api/events");
      source.onopen = () => {
        if (attempts > 0) void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
        attempts = 0;
        setConnection("live");
      };
      source.onerror = () => {
        source?.close();
        if (closed) return;
        setConnection("reconnecting");
        attempts += 1;
        retry = setTimeout(connect, Math.min(1000 * 2 ** attempts, 15_000));
      };
      source.addEventListener("job.created", handle("job.created"));
      source.addEventListener("job.updated", handle("job.updated"));
      source.addEventListener("job.deleted", (message: MessageEvent<string>) => {
        const job = JSON.parse(message.data) as { id: string };
        queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs) =>
          applyJobEvent(jobs, { type: "job.deleted", job }),
        );
      });
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      source?.close();
    };
  }, [queryClient, t]);

  return <ConnectionContext.Provider value={connection}>{children}</ConnectionContext.Provider>;
}
