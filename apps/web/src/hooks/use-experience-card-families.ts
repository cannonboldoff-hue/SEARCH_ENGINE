import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SavedCardFamily } from "@/types";

export const EXPERIENCE_CARD_FAMILIES_QUERY_KEY = ["experience-card-families"] as const;

export function useExperienceCardFamilies() {
  return useQuery({
    queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY,
    queryFn: () => api<SavedCardFamily[]>("/me/experience-card-families"),
  });
}
