"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { EmailChannelOut, NotificationsOut, VerifyOut } from "@/api/types";

const key = ["notifications"] as const;

export function useNotifications(enabled: boolean) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });

  const status = useQuery({
    queryKey: key,
    queryFn: () => apiRequest<NotificationsOut>("GET", "/notifications"),
    enabled,
    retry: false,
  });

  const subscribe = useMutation({
    mutationFn: (email: string) =>
      apiRequest<EmailChannelOut>("POST", "/notifications/email", { email }),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: () => apiRequest<null>("DELETE", "/notifications/email"),
    onSuccess: refresh,
  });

  return { status, subscribe, remove };
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (token: string) =>
      apiRequest<VerifyOut>("POST", "/notifications/email/verify", { token }),
  });
}
