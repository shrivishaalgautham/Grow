"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiBaseUrl, apiRequest, isFixtureMode } from "@/api/client";
import { simulateGoogleSignIn } from "@/api/fixture";
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

  const signInWithGoogle = useCallback(() => {
    if (!isFixtureMode) {
      // Cross-origin redirect to the backend's OAuth entrypoint, not an internal route.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `${apiBaseUrl}/api/auth/google/start`;
      return;
    }
    const session = simulateGoogleSignIn();
    queryClient.removeQueries();
    storeToken(session.token, session.expires_at);
  }, [queryClient]);

  return { token, ready, start, end, deleteAccount, adoptToken, signInWithGoogle };
}
