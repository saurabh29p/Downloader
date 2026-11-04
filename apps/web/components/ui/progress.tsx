import { cn } from "@/lib/utils";

/** Accessible progress bar. Pass value=null for an indeterminate bar. */
function Progress({
  value,
  className,
  "aria-label": ariaLabel,
}: {
  value: number | null;
  className?: string;
  "aria-label"?: string;
}) {
  const indeterminate = value == null;
  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : value}
      aria-valuetext={indeterminate ? undefined : `${value}%`}
      data-slot="progress"
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-secondary", className)}
    >
      <div
        className={cn(
          "h-full bg-primary transition-[width] duration-(--duration-normal) ease-(--ease-standard)",
          indeterminate && "w-1/3 animate-[indeterminate_1.4s_ease-in-out_infinite]",
        )}
        style={indeterminate ? undefined : { width: `${value}%` }}
      />
    </div>
  );
}

export { Progress };
