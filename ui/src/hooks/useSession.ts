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

  const snapshot = useSyncExternalStore(
    subscribeToToken,
    tokenSnapshot,
    serverTokenSnapshot,
  );
  const ready = snapshot !== undefined;
  const token = snapshot ?? null;

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

  const deleteAccount = useMutation({
    mutationFn: () => apiRequest<null>("DELETE", "/auth/account"),
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

  return { token, ready, start, end, deleteAccount, adoptToken };
}
