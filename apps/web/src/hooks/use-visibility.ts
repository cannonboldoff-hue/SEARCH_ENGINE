import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { VisibilitySettingsResponse } from "@/types";

export const VISIBILITY_QUERY_KEY = ["visibility"] as const;

const defaultVisibility: VisibilitySettingsResponse = {
  open_to_work: false,
  open_to_contact: false,
  work_preferred_locations: [],
  work_preferred_salary_min: null,
  work_preferred_salary_max: null,
};

export function useVisibility() {
  return useQuery({
    queryKey: VISIBILITY_QUERY_KEY,
    queryFn: async () => {
      try {
        return await api<VisibilitySettingsResponse>("/me/visibility");
      } catch {
        return defaultVisibility;
      }
    },
  });
}

export { defaultVisibility };
