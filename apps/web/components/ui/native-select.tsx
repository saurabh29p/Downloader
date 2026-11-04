import { ChevronDownIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** A styled native <select>: accessible, tiny, and uses the phone's own picker. */
function NativeSelect({
  className,
  icon,
  iconOnlyOnPhone = false,
  ...props
}: ComponentProps<"select"> & { icon?: ReactNode; iconOnlyOnPhone?: boolean }) {
  return (
    <div className="relative inline-flex items-center">
      {icon && (
        <span className="pointer-events-none absolute start-3 flex text-muted-foreground [&_svg]:size-4">
          {icon}
        </span>
      )}
      <select
        className={cn(
          "h-11 cursor-pointer appearance-none rounded-md border border-transparent bg-transparent text-sm hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
          icon ? "ps-9" : "ps-3",
          iconOnlyOnPhone
            ? "w-11 pe-2 text-transparent sm:w-auto sm:pe-8 sm:text-foreground [&>option]:text-foreground"
            : "pe-8",
          className,
        )}
        {...props}
      />
      <ChevronDownIcon
        className={cn(
          "pointer-events-none absolute end-2.5 size-4 text-muted-foreground",
          iconOnlyOnPhone && "hidden sm:block",
        )}
        aria-hidden="true"
      />
    </div>
  );
}

export { NativeSelect };
