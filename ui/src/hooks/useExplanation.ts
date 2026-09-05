"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequestOrDemo } from "@/api/client";
import type { ExplanationOut } from "@/api/types";

export function useExplanation(symbol: string | null) {
  return useQuery({
    queryKey: ["explanation", symbol],
    queryFn: () =>
      apiRequestOrDemo<ExplanationOut>("GET", `/symbols/${encodeURIComponent(symbol!)}/explanation`),
    enabled: symbol !== null,
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.status === "pending" && query.state.dataUpdateCount < 3 ? 4_000 : false,
  });
}
