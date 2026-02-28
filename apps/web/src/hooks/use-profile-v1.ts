import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Person } from "@/types";

export const PROFILE_SCHEMA_QUERY_KEY = ["me", "profile-schema"] as const;

export function useProfileSchema() {
  return useQuery({
    queryKey: PROFILE_SCHEMA_QUERY_KEY,
    queryFn: () => api<Person>("/me/profile-schema"),
  });
}
