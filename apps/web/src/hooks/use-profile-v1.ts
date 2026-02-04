import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Person } from "@/types";

export const PROFILE_V1_QUERY_KEY = ["me", "profile-v1"] as const;

export function useProfileV1() {
  return useQuery({
    queryKey: PROFILE_V1_QUERY_KEY,
    queryFn: () => api<Person>("/me/profile-v1"),
  });
}
