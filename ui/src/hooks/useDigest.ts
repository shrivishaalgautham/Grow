"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { DigestOut } from "@/api/types";

export const digestKey = ["digest"] as const;

export function useDigest(enabled: boolean) {
  return useQuery({
    queryKey: digestKey,
    queryFn: () => apiRequest<DigestOut>("GET", "/watchlist/digest"),
    enabled,
    refetchInterval: 90_000,
    staleTime: 30_000,
  });
}
