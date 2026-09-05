"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequestOrDemo } from "@/api/client";
import type { CatalystsOut } from "@/api/types";

export function useCatalysts(symbol: string | null) {
  return useQuery({
    queryKey: ["catalysts", symbol],
    queryFn: () =>
      apiRequestOrDemo<CatalystsOut>(
        "GET",
        `/symbols/${encodeURIComponent(symbol!)}/catalysts`,
      ),
    enabled: symbol !== null,
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" && query.state.dataUpdateCount < 2
        ? 4_000
        : false,
  });
}
