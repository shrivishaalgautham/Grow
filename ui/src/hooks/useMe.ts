"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { MeOut } from "@/api/types";

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiRequest<MeOut>("GET", "/auth/me"),
    enabled,
    staleTime: 10 * 60_000,
    retry: false,
  });
}
