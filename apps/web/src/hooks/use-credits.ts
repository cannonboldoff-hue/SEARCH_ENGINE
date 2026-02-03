"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCredits() {
  return useQuery({
    queryKey: ["credits"],
    queryFn: () => api<{ balance: number }>("/me/credits"),
  });
}
