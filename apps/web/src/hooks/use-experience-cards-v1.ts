import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ExperienceCardV1 } from "@/types";

export const EXPERIENCE_CARDS_V1_QUERY_KEY = ["me", "experience-cards-v1"] as const;

export function useExperienceCardsV1(statusFilter?: string | null) {
  return useQuery({
    queryKey: [...EXPERIENCE_CARDS_V1_QUERY_KEY, statusFilter ?? "all"],
    queryFn: () => {
      const params = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
      return api<ExperienceCardV1[]>(`/me/experience-cards-v1${params}`);
    },
  });
}
