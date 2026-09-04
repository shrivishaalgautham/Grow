"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { DigestOut, SeenOut } from "@/api/types";
import { digestKey } from "./useDigest";

function markSeen(digest: DigestOut, symbols: string[] | "all"): DigestOut {
  const target = symbols === "all" ? null : new Set(symbols);
  const items = digest.items.map((item) =>
    target && !target.has(item.symbol)
      ? item
      : {
          ...item,
          attention: "quiet" as const,
          is_changed: false,
          signals: [],
          change_since_seen_pct: 0,
        },
  );
  return {
    ...digest,
    items,
    changed_count: items.filter((item) => item.is_changed).length,
    ...(symbols === "all"
      ? { last_reviewed_at: new Date().toISOString(), away_duration_seconds: 0 }
      : {}),
  };
}

export function useSeen() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (symbols: string[] | "all") =>
      apiRequest<SeenOut>("POST", "/watchlist/seen", { symbols }),
    onMutate: async (symbols) => {
      await queryClient.cancelQueries({ queryKey: digestKey });
      const previous = queryClient.getQueryData<DigestOut>(digestKey);
      if (previous) {
        queryClient.setQueryData(digestKey, markSeen(previous, symbols));
      }
      return { previous };
    },
    onError: (_error, _symbols, context) => {
      if (context?.previous) queryClient.setQueryData(digestKey, context.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: digestKey });
      queryClient.invalidateQueries({ queryKey: ["briefing"] });
    },
  });
}
