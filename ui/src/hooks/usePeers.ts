"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { PeersOut } from "@/api/types";

export function usePeers(symbol: string | null) {
  return useQuery({
    queryKey: ["peers", symbol],
    queryFn: () =>
      apiRequest<PeersOut>(
        "GET",
        `/symbols/${encodeURIComponent(symbol!)}/peers`,
      ),
    enabled: symbol !== null,
    staleTime: 10 * 60_000,
  });
}
