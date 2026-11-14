import { act, render, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  QueryClient,
  QueryClientProvider,
  hashKey,
  share,
  useInfiniteQuery,
  useMutation,
  useQuery,
} from "./query";

function setup(retry: boolean | number = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry, staleTime: 10_000 } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
};

describe("keys and sharing", () => {
  it("hashes object keys in any order to the same entry", () => {
    expect(hashKey(["a", { x: 1, y: 2 }])).toBe(hashKey(["a", { y: 2, x: 1 }]));
    expect(hashKey(["a", 1])).not.toBe(hashKey(["a", "1"]));
  });

  it("keeps unchanged parts of new data", () => {
    const prev = { list: [{ id: 1 }, { id: 2 }], meta: { n: 2 } };
    const next = share(prev, { list: [{ id: 1 }, { id: 3 }], meta: { n: 2 } });
    expect(next).not.toBe(prev);
    expect(next.list[0]).toBe(prev.list[0]);
    expect(next.meta).toBe(prev.meta);
    expect(share(prev, structuredClone(prev))).toBe(prev);
  });
});

describe("useQuery", () => {
  it("shares one fetch between components and is pending until data arrives", async () => {
    const { wrapper } = setup();
    const answer = deferred<string>();
    const queryFn = vi.fn(() => answer.promise);
    const a = renderHook(() => useQuery({ queryKey: ["k"], queryFn }), { wrapper });
    const b = renderHook(() => useQuery({ queryKey: ["k"], queryFn }), { wrapper });
    expect(a.result.current.isPending).toBe(true);
    await act(async () => answer.resolve("hello"));
    expect(a.result.current.data).toBe("hello");
    expect(b.result.current.data).toBe("hello");
    expect(queryFn).toHaveBeenCalledTimes(1);
  });

  it("is pending and does not fetch while disabled", () => {
    const { wrapper } = setup();
    const queryFn = vi.fn(async () => 1);
    const { result } = renderHook(() => useQuery({ queryKey: ["off"], queryFn, enabled: false }), {
      wrapper,
    });
    expect(result.current.isPending).toBe(true);
    expect(queryFn).not.toHaveBeenCalled();
  });

  it("refetches on mount only when the data is stale", async () => {
    const { client, wrapper } = setup();
    const queryFn = vi.fn(async () => "fresh");
    client.setQueryData(["s"], "cached");
    const first = renderHook(() => useQuery({ queryKey: ["s"], queryFn }), { wrapper });
    expect(first.result.current.data).toBe("cached");
    expect(queryFn).not.toHaveBeenCalled();
    first.unmount();
    const second = renderHook(() => useQuery({ queryKey: ["s"], queryFn, staleTime: 0 }), {
      wrapper,
    });
    await waitFor(() => expect(second.result.current.data).toBe("fresh"));
  });

  it("invalidation refetches mounted queries with the same key prefix only", async () => {
    const { client, wrapper } = setup();
    let n = 0;
    const lib = vi.fn(async () => ++n);
    const other = vi.fn(async () => "x");
    const { result } = renderHook(
      () => ({
        lib: useQuery({ queryKey: ["library", { q: "a" }], queryFn: lib }),
        other: useQuery({ queryKey: ["jobs"], queryFn: other }),
      }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.lib.data).toBe(1));
    await act(() => client.invalidateQueries({ queryKey: ["library"] }));
    expect(result.current.lib.data).toBe(2);
    expect(other).toHaveBeenCalledTimes(1);
  });

  it("drops an older answer when a refetch was asked for during it", async () => {
    const { client, wrapper } = setup();
    const answers = [deferred<string>(), deferred<string>()];
    let call = 0;
    const queryFn = () => answers[call++]!.promise;
    const { result } = renderHook(() => useQuery({ queryKey: ["r"], queryFn }), { wrapper });
    void client.invalidateQueries({ queryKey: ["r"] }); // e.g. after adding a download
    await act(async () => answers[1]!.resolve("after the change"));
    await act(async () => answers[0]!.resolve("before the change"));
    expect(result.current.data).toBe("after the change");
  });

  it("retries, then keeps the last good data with the error", async () => {
    vi.useFakeTimers();
    try {
      const { wrapper } = setup(1);
      let ok = true;
      const queryFn = vi.fn(async () => {
        if (ok) return "good";
        throw new Error("down");
      });
      const { result } = renderHook(() => useQuery({ queryKey: ["e"], queryFn }), { wrapper });
      await act(async () => {});
      expect(result.current.data).toBe("good");
      ok = false;
      await act(async () => void result.current.refetch());
      expect(queryFn).toHaveBeenCalledTimes(2);
      expect(result.current.isError).toBe(false); // waiting for the retry (1 s)
      await act(async () => vi.advanceTimersByTimeAsync(1000));
      expect(queryFn).toHaveBeenCalledTimes(3);
      expect(result.current.isError).toBe(true);
      expect(result.current.error?.message).toBe("down");
      expect(result.current.data).toBe("good");
    } finally {
      vi.useRealTimers();
    }
  });

  it("ignores updaters that return undefined", () => {
    const { client } = setup();
    client.setQueryData<number[]>(["u"], (old) => (old ? [...old, 1] : undefined));
    expect(client.getQueryData(["u"])).toBeUndefined();
    client.setQueryData<number[]>(["u"], [1]);
    client.setQueryData<number[]>(["u"], (old) => (old ? [...old, 2] : undefined));
    expect(client.getQueryData(["u"])).toEqual([1, 2]);
  });

  it("keeps the same data object when a refetch changed nothing", async () => {
    const { wrapper } = setup();
    const queryFn = async () => ({ files: [{ name: "a.pdf" }] });
    const effect = vi.fn();
    function Item() {
      const { data } = useQuery({ queryKey: ["same"], queryFn });
      effect(data);
      return null;
    }
    const { rerender } = render(<Item />, { wrapper });
    await waitFor(() => expect(effect).toHaveBeenLastCalledWith({ files: [{ name: "a.pdf" }] }));
    const first = effect.mock.lastCall![0];
    rerender(<Item />);
    expect(effect.mock.lastCall![0]).toBe(first);
  });
});

describe("useInfiniteQuery", () => {
  it("loads the next page and refetches every shown page", async () => {
    const { client, wrapper } = setup();
    let version = "v1";
    const queryFn = vi.fn(async ({ pageParam }: { pageParam: number }) => ({
      items: [`${version}-${pageParam}`],
      next: pageParam < 3 ? pageParam + 1 : null,
    }));
    const { result } = renderHook(
      () =>
        useInfiniteQuery({
          queryKey: ["pages"],
          queryFn,
          initialPageParam: 1,
          getNextPageParam: (last) => last.next,
        }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(1));
    expect(result.current.hasNextPage).toBe(true);
    await act(() => result.current.fetchNextPage());
    expect(result.current.data?.pages.map((p) => p.items[0])).toEqual(["v1-1", "v1-2"]);
    version = "v2";
    await act(() => client.invalidateQueries({ queryKey: ["pages"] }));
    expect(result.current.data?.pages.map((p) => p.items[0])).toEqual(["v2-1", "v2-2"]);
    expect(result.current.data?.pageParams).toEqual([1, 2]);
  });
});

describe("useMutation", () => {
  it("runs the callbacks in order and reports the state", async () => {
    const { wrapper } = setup();
    const calls: string[] = [];
    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: async (n: number) => {
            calls.push(`fn ${n}`);
            return n * 2;
          },
          onMutate: (n) => void calls.push(`mutate ${n}`),
          onSuccess: (data, n) => void calls.push(`success ${data} ${n}`),
        }),
      { wrapper },
    );
    expect(result.current.isIdle).toBe(true);
    act(() => result.current.mutate(2));
    expect(result.current.isPending).toBe(true);
    expect(result.current.variables).toBe(2);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(4);
    expect(calls).toEqual(["mutate 2", "fn 2", "success 4 2"]);
  });

  it("reports errors without throwing from mutate", async () => {
    const { wrapper } = setup();
    const onError = vi.fn();
    const { result } = renderHook(
      () =>
        useMutation({
          mutationFn: async () => {
            throw new Error("nope");
          },
          onError: (error) => onError(error),
        }),
      { wrapper },
    );
    act(() => result.current.mutate());
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("nope");
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "nope" }));
  });
});
