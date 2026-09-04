"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { ProvidersHealthOut } from "@/api/types";

export function useHealth(enabled: boolean) {
  return useQuery({
    queryKey: ["health-providers"],
    queryFn: () => apiRequest<ProvidersHealthOut>("GET", "/health/providers"),
    enabled,
    refetchInterval: 60_000,
    retry: false,
  });
}
