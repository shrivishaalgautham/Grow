"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import {
  clearToken,
  serverTokenSnapshot,
  storeToken,
  subscribeToToken,
  tokenSnapshot,
} from "@/api/session";
import type { SessionCreate, SessionOut } from "@/api/types";

export function useSession() {
  const queryClient = useQueryClient();

  const token = useSyncExternalStore(
    subscribeToToken,
    tokenSnapshot,
    serverTokenSnapshot,
  );
  const ready = useSyncExternalStore(
    subscribeToToken,
    () => true,
    () => false,
  );

  const start = useMutation({
    mutationFn: (input: SessionCreate) =>
      apiRequest<SessionOut>("POST", "/auth/session", input),
    onSuccess: (session) => {
      queryClient.removeQueries();
      storeToken(session.token, session.expires_at);
    },
  });

  const end = useMutation({
    mutationFn: () => apiRequest<null>("DELETE", "/auth/session"),
    onSuccess: () => {
      queryClient.removeQueries();
      clearToken();
    },
  });

  const adoptToken = useCallback(
    (value: string) => {
      queryClient.removeQueries();
      storeToken(value);
    },
    [queryClient],
  );

  return { token, ready, start, end, adoptToken };
}
