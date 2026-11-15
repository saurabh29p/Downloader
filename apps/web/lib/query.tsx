"use client";

/**
 * A small server-state cache with the parts of TanStack Query's API that AnyGet uses
 * (useQuery, useInfiniteQuery, useMutation, useQueryClient; getQueryData, setQueryData,
 * invalidateQueries). TanStack Query cost ~12 KB gzip in the shell of every page; this
 * file is ~2 KB. The behaviour follows TanStack Query 5's defaults:
 *
 * - one cache entry per key (keys are hashed with sorted object keys), shared by every
 *   component; a fetch that is already running is reused when another component mounts;
 * - data is refetched on mount when it is missing, invalidated or older than `staleTime`;
 * - `refetch()` and `invalidateQueries()` start a new fetch even when one is running,
 *   and the older answer is dropped (it may predate the change that caused the refetch);
 * - failed fetches retry `retry` times (1 s, 2 s, 4 s… up to 30 s); an error keeps the
 *   last good data; a disabled query without data is `isPending`;
 * - new data is structurally shared with the old (unchanged parts keep their identity),
 *   so effects that depend on `data` don't re-run when a refetch changed nothing;
 * - `setQueryData` with an updater that returns `undefined` changes nothing.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

export type QueryKey = readonly unknown[];
type Status = "pending" | "error" | "success";
type Retry = boolean | number;

type QueryState<T> = {
  data: T | undefined;
  error: Error | null;
  status: Status;
  updatedAt: number;
  fetching: boolean;
  nextPage: boolean;
  invalid: boolean;
};

const isPlain = (value: unknown): value is Record<string, unknown> => {
  if (Object.prototype.toString.call(value) !== "[object Object]") return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

export const hashKey = (key: QueryKey): string =>
  JSON.stringify(key, (_, value: unknown) =>
    isPlain(value)
      ? Object.fromEntries(
          Object.keys(value)
            .sort()
            .map((k) => [k, value[k]]),
        )
      : value,
  );

/** `next`, reusing every part of `prev` that is deeply equal (TanStack's replaceEqualDeep). */
export function share<T>(prev: unknown, next: T): T {
  if (prev === next) return next;
  const arrays = Array.isArray(prev) && Array.isArray(next);
  if (!arrays && !(isPlain(prev) && isPlain(next))) return next;
  const a = prev as Record<string, unknown>;
  const b = next as Record<string, unknown>;
  const keys = Object.keys(b);
  const out: Record<string, unknown> = arrays ? ([] as unknown as Record<string, unknown>) : {};
  let same = keys.length === Object.keys(a).length;
  for (const key of keys) {
    out[key] = share(a[key], b[key]);
    if (out[key] !== a[key] || !(key in a)) same = false;
  }
  return (same ? prev : out) as T;
}

class Query<T = unknown> {
  state: QueryState<T> = {
    data: undefined,
    error: null,
    status: "pending",
    updatedAt: 0,
    fetching: false,
    nextPage: false,
    invalid: false,
  };
  /** How to fetch it and how often to retry: set by the mounted hooks (`configure`). */
  private fetcher?: () => Promise<T>;
  private retry: Retry = 3;
  /** Mounted, enabled hooks: only these queries refetch when invalidated. */
  active = 0;
  private listeners = new Set<() => void>();
  private running?: Promise<void>;
  private generation = 0;

  constructor(readonly key: QueryKey) {}

  configure(fetcher: () => Promise<T>, retry: Retry) {
    this.fetcher = fetcher;
    this.retry = retry;
  }

  /** A mounted, enabled hook: fetch when missing, invalidated or stale; poll if asked. */
  attach(staleTime: number, interval?: number) {
    this.active++;
    const { data, invalid, updatedAt } = this.state;
    if (data === undefined || invalid || Date.now() - updatedAt >= staleTime) void this.fetch();
    const timer = interval ? setInterval(() => void this.fetch(), interval) : undefined;
    return () => {
      this.active--;
      clearInterval(timer);
    };
  }

  /** Stable across renders, like TanStack's (safe in effect dependencies). */
  refetch = () => this.fetch(undefined, true);

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  set(patch: Partial<QueryState<T>>) {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener();
  }

  /** Runs `run` (default: the hook's fetcher). `force` drops a fetch already running. */
  fetch(run: (() => Promise<T>) | undefined = this.fetcher, force = false, nextPage = false) {
    if (!run) return Promise.resolve();
    if (this.running && !force) return this.running;
    const generation = ++this.generation;
    const current = () => generation === this.generation;
    const retries = this.retry === true ? Infinity : this.retry === false ? 0 : this.retry;
    this.set({ fetching: true, nextPage });
    const done = (async () => {
      for (let failures = 0; ; failures++) {
        try {
          const data = await run();
          if (current()) this.resolve(data);
          return;
        } catch (error) {
          if (!current()) return;
          if (failures < retries) {
            await new Promise((wake) => setTimeout(wake, Math.min(1000 * 2 ** failures, 30_000)));
            if (!current()) return;
            continue;
          }
          const err = error instanceof Error ? error : new Error(String(error));
          this.set({
            error: err,
            status: "error",
            fetching: false,
            nextPage: false,
            invalid: false,
          });
          return;
        }
      }
    })().finally(() => {
      if (current()) this.running = undefined;
    });
    this.running = done;
    return done;
  }

  resolve(data: T) {
    this.set({
      data: share(this.state.data, data),
      error: null,
      status: "success",
      updatedAt: Date.now(),
      fetching: false,
      nextPage: false,
      invalid: false,
    });
  }
}

type QueryDefaults = { staleTime?: number; retry?: Retry; refetchOnWindowFocus?: boolean };

export class QueryClient {
  private queries = new Map<string, Query>();

  constructor(readonly config: { defaultOptions?: { queries?: QueryDefaults } } = {}) {}

  /** The cache entry for a key (made on first use). */
  query<T>(key: QueryKey): Query<T> {
    const hash = hashKey(key);
    let query = this.queries.get(hash);
    if (!query) this.queries.set(hash, (query = new Query(key)));
    return query as Query<T>;
  }

  getQueryData<T>(key: QueryKey): T | undefined {
    return this.queries.get(hashKey(key))?.state.data as T | undefined;
  }

  setQueryData<T>(key: QueryKey, updater: T | undefined | ((old: T | undefined) => T | undefined)) {
    const query = this.query<T>(key);
    const data =
      typeof updater === "function"
        ? (updater as (old: T | undefined) => T | undefined)(query.state.data)
        : updater;
    if (data !== undefined) query.resolve(data);
    return data;
  }

  /** Marks every query whose key starts with `queryKey` stale; mounted ones refetch now. */
  invalidateQueries({ queryKey = [] }: { queryKey?: QueryKey } = {}): Promise<void> {
    const prefix = queryKey.map((part) => hashKey([part]));
    const fetches: Promise<void>[] = [];
    for (const query of this.queries.values()) {
      if (!prefix.every((part, i) => part === hashKey([query.key[i]]))) continue;
      query.set({ invalid: true });
      if (query.active) fetches.push(query.fetch(undefined, true));
    }
    return Promise.all(fetches).then(() => undefined);
  }
}

const ClientContext = createContext<QueryClient | null>(null);

export function QueryClientProvider({
  client,
  children,
}: {
  client: QueryClient;
  children: ReactNode;
}) {
  return <ClientContext.Provider value={client}>{children}</ClientContext.Provider>;
}

export function useQueryClient(): QueryClient {
  const client = useContext(ClientContext);
  if (!client) throw new Error("No QueryClient set, use QueryClientProvider to set one");
  return client;
}

type BaseOptions = {
  queryKey: QueryKey;
  enabled?: boolean;
  staleTime?: number;
  retry?: Retry;
  refetchInterval?: number;
};

/** Subscribes to one cache entry and fetches it on mount (and on an interval) when needed. */
function useEntry<T>(options: BaseOptions, fetcher: (client: QueryClient) => Promise<T>) {
  const client = useQueryClient();
  const query = client.query<T>(options.queryKey);
  const defaults = client.config.defaultOptions?.queries ?? {};
  const enabled = options.enabled !== false;
  const staleTime = options.staleTime ?? defaults.staleTime ?? 0;
  const interval = options.refetchInterval;
  const state = useSyncExternalStore(
    query.subscribe,
    () => query.state,
    () => query.state,
  );

  const retry = options.retry ?? defaults.retry ?? 3;

  // The latest fetch function and retry count, before the mount effect below uses them.
  useEffect(() => query.configure(() => fetcher(client), retry));
  useEffect(
    () => (enabled ? query.attach(staleTime, interval) : undefined),
    [query, enabled, staleTime, interval],
  );

  return { query, state };
}

type ResultBase = {
  isFetching: boolean;
  isRefetching: boolean;
  refetch: () => Promise<void>;
};
/** Narrows like TanStack's: after `isPending` and `isError` checks, `data` is set. */
export type QueryResult<T> = ResultBase &
  (
    | { isPending: true; isError: false; isSuccess: false; data: undefined; error: null }
    | { isPending: false; isError: true; isSuccess: false; data: undefined; error: Error }
    | { isPending: false; isError: true; isSuccess: false; data: T; error: Error }
    | { isPending: false; isError: false; isSuccess: true; data: T; error: null }
  );

function result<T>(query: Query<T>, state: QueryState<T>): QueryResult<T> {
  const pending = state.status === "pending";
  return {
    data: state.data,
    error: state.error,
    isPending: pending,
    isError: state.status === "error",
    isSuccess: state.status === "success",
    isFetching: state.fetching,
    isRefetching: state.fetching && !pending,
    refetch: query.refetch,
  } as QueryResult<T>;
}

export function useQuery<T>(
  options: BaseOptions & {
    queryFn: (context: { queryKey: QueryKey; client: QueryClient }) => Promise<T>;
  },
): QueryResult<T> {
  const { query, state } = useEntry<T>(options, (client) =>
    options.queryFn({ queryKey: options.queryKey, client }),
  );
  return result(query, state);
}

export type InfiniteData<P, Param> = { pages: P[]; pageParams: Param[] };
type NextParam<P, Param> = (
  lastPage: P,
  allPages: P[],
  lastParam: Param,
  allParams: Param[],
) => Param | undefined | null;

const nextParamOf = <P, Param>(data: InfiniteData<P, Param>, next: NextParam<P, Param>) =>
  data.pages.length
    ? next(data.pages.at(-1)!, data.pages, data.pageParams.at(-1)!, data.pageParams)
    : undefined;

export function useInfiniteQuery<P, Param>(
  options: BaseOptions & {
    queryFn: (context: { queryKey: QueryKey; pageParam: Param }) => Promise<P>;
    initialPageParam: Param;
    getNextPageParam: NextParam<P, Param>;
  },
): QueryResult<InfiniteData<P, Param>> & {
  fetchNextPage: () => Promise<void>;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
} {
  const { queryKey, queryFn, initialPageParam, getNextPageParam } = options;
  // A refetch loads again as many pages as are shown, each from the page before it.
  const { query, state } = useEntry<InfiniteData<P, Param>>(options, async (client) => {
    const count = client.getQueryData<InfiniteData<P, Param>>(queryKey)?.pages.length || 1;
    const data: InfiniteData<P, Param> = { pages: [], pageParams: [] };
    let pageParam = initialPageParam;
    for (let i = 0; i < count; i++) {
      if (i > 0) {
        const next = nextParamOf(data, getNextPageParam);
        if (next == null) break;
        pageParam = next;
      }
      data.pages.push(await queryFn({ queryKey, pageParam }));
      data.pageParams.push(pageParam);
    }
    return data;
  });
  const next = state.data ? nextParamOf(state.data, getNextPageParam) : undefined;
  return {
    ...result(query, state),
    hasNextPage: next != null,
    isFetchingNextPage: state.fetching && state.nextPage,
    fetchNextPage: () => {
      const shown = query.state.data;
      if (next == null || !shown) return Promise.resolve();
      return query.fetch(
        async () => {
          const page = await queryFn({ queryKey, pageParam: next });
          return { pages: [...shown.pages, page], pageParams: [...shown.pageParams, next] };
        },
        false,
        true,
      );
    },
  };
}

type MutationState<D, V> = {
  status: "idle" | "pending" | "error" | "success";
  data: D | undefined;
  error: Error | null;
  variables: V | undefined;
};

export function useMutation<D = unknown, V = void>(options: {
  mutationFn: (variables: V) => Promise<D>;
  onMutate?: (variables: V) => unknown;
  onSuccess?: (data: D, variables: V) => unknown;
  onError?: (error: Error, variables: V) => unknown;
}) {
  const [state, setState] = useState<MutationState<D, V>>({
    status: "idle",
    data: undefined,
    error: null,
    variables: undefined,
  });
  const latest = useRef(options);
  const calls = useRef(0);
  useEffect(() => {
    latest.current = options;
  });

  const mutateAsync = useCallback(async (variables: V): Promise<D> => {
    const call = ++calls.current;
    // Only the latest call updates the state; every call runs its callbacks.
    const update = (next: MutationState<D, V>) => {
      if (call === calls.current) setState(next);
    };
    const { mutationFn, onMutate, onSuccess, onError } = latest.current;
    update({ status: "pending", data: undefined, error: null, variables });
    try {
      await onMutate?.(variables);
      const data = await mutationFn(variables);
      await onSuccess?.(data, variables);
      update({ status: "success", data, error: null, variables });
      return data;
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      await onError?.(err, variables);
      update({ status: "error", data: undefined, error: err, variables });
      throw err;
    }
  }, []);
  const mutate = useCallback(
    (variables: V) => void mutateAsync(variables).catch(() => undefined),
    [mutateAsync],
  );

  return {
    ...state,
    isIdle: state.status === "idle",
    isPending: state.status === "pending",
    isError: state.status === "error",
    isSuccess: state.status === "success",
    mutate,
    mutateAsync,
    reset: () => setState({ status: "idle", data: undefined, error: null, variables: undefined }),
  };
}
