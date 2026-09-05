"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequestOrDemo } from "@/api/client";
import type { SymbolSearchOut } from "@/api/types";

export function useSymbolSearch(query: string) {
  const trimmed = query.trim().slice(0, 32);

  return useQuery({
    queryKey: ["symbol-search", trimmed],
    queryFn: () =>
      apiRequestOrDemo<SymbolSearchOut[]>(
        "GET",
        `/symbols/search?q=${encodeURIComponent(trimmed)}`,
      ),
    enabled: trimmed.length >= 2,
    staleTime: 5 * 60_000,
  });
}
