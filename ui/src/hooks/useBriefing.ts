"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { BriefingOut } from "@/api/types";

export function useBriefing(enabled: boolean) {
  return useQuery({
    queryKey: ["briefing"],
    queryFn: () => apiRequest<BriefingOut>("GET", "/watchlist/briefing"),
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
