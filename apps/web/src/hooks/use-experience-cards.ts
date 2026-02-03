import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ExperienceCard } from "@/types";

export const EXPERIENCE_CARDS_QUERY_KEY = ["experience-cards"] as const;

export function useExperienceCards() {
  return useQuery({
    queryKey: EXPERIENCE_CARDS_QUERY_KEY,
    queryFn: () => api<ExperienceCard[]>("/me/experience-cards"),
  });
}
