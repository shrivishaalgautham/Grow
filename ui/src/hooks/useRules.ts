"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Rule, RuleActionInput, RuleCompileOut, RuleListItem, RuleOut } from "@/api/types";

const rulesKey = ["rules"] as const;

export function useRules(enabled: boolean) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: rulesKey });

  const list = useQuery({
    queryKey: rulesKey,
    queryFn: () => apiRequest<RuleListItem[]>("GET", "/rules"),
    enabled,
  });

  const compile = useMutation({
    mutationFn: (text: string) =>
      apiRequest<RuleCompileOut>("POST", "/rules/compile", { text }),
  });

  const create = useMutation({
    mutationFn: (input: { nl_text: string; rule: Rule; actions?: RuleActionInput[] }) =>
      apiRequest<RuleOut>("POST", "/rules", input),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: (id: string) => apiRequest<null>("DELETE", `/rules/${id}`),
    onSuccess: refresh,
  });

  return { list, compile, create, remove };
}
