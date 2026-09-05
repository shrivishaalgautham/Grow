"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequestOrDemo } from "@/api/client";
import type { HistoryOut } from "@/api/types";

export function useHistory(symbol: string | null) {
  return useQuery({
    queryKey: ["history", symbol],
    queryFn: () =>
      apiRequestOrDemo<HistoryOut>(
        "GET",
        `/symbols/${encodeURIComponent(symbol!)}/history?days=90`,
      ),
    enabled: symbol !== null,
    staleTime: 10 * 60_000,
  });
}
