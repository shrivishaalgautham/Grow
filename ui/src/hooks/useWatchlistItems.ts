"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Item } from "@/api/types";
import { digestKey } from "./useDigest";

export function useWatchlistItems() {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: digestKey });

  const add = useMutation({
    mutationFn: (symbol: string) =>
      apiRequest<Item>("POST", "/watchlist/items", { symbol }),
    onSuccess: () => {
      refresh();
      setTimeout(refresh, 3_000);
    },
  });

  const remove = useMutation({
    mutationFn: (symbol: string) =>
      apiRequest<null>(
        "DELETE",
        `/watchlist/items/${encodeURIComponent(symbol)}`,
      ),
    onSuccess: refresh,
  });

  return { add, remove };
}
