import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ExperienceCardSchema } from "@/types";

export const EXPERIENCE_CARDS_SCHEMA_QUERY_KEY = ["me", "experience-cards-schema"] as const;

export function useExperienceCardsSchema(statusFilter?: string | null) {
  return useQuery({
    queryKey: [...EXPERIENCE_CARDS_SCHEMA_QUERY_KEY, statusFilter ?? "all"],
    queryFn: () => {
      const params = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
      return api<ExperienceCardSchema[]>(`/me/experience-cards-schema${params}`);
    },
  });
}
