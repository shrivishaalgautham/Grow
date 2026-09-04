"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { EvidenceOut } from "@/api/types";

export function useEvidence(enabled: boolean, days = 90) {
  return useQuery({
    queryKey: ["evidence", days],
    queryFn: () =>
      apiRequest<EvidenceOut>("GET", `/evidence/noise-reduction?days=${days}`),
    enabled,
    staleTime: 30 * 60_000,
  });
}
