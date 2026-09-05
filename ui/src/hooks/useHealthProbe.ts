"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";

export interface Probe {
  ok: boolean;
  latencyMs: number;
}

export function useHealthProbe() {
  return useQuery({
    queryKey: ["health-probe"],
    queryFn: async (): Promise<Probe> => {
      const started = performance.now();
      try {
        await apiRequest<{ ok: true }>("GET", "/health");
        return { ok: true, latencyMs: Math.round(performance.now() - started) };
      } catch {
        return { ok: false, latencyMs: Math.round(performance.now() - started) };
      }
    },
    staleTime: 30_000,
    retry: false,
  });
}
