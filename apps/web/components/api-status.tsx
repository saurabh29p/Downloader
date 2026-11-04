"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Shows whether the FastAPI core is reachable through the /api rewrite. */
export function ApiStatus() {
  const t = useTranslations("Status");
  const { isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const state = isPending ? "checking" : isError ? "offline" : "online";

  return (
    <div className="flex items-center gap-3" data-testid="api-status" data-state={state}>
      <p role="status" aria-live="polite" className="flex items-center gap-2 text-sm">
        <span
          aria-hidden="true"
          className={cn(
            "size-2.5 rounded-full",
            state === "checking" && "animate-pulse bg-muted-foreground",
            state === "online" && "bg-success",
            state === "offline" && "bg-destructive",
          )}
        />
        {t(state)}
      </p>
      {isError && (
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          {t("retry")}
        </Button>
      )}
    </div>
  );
}
