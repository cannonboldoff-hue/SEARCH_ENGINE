import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { BioResponse } from "@/types";

export const BIO_QUERY_KEY = ["bio"] as const;

export function useBio() {
  return useQuery({
    queryKey: BIO_QUERY_KEY,
    queryFn: () => api<BioResponse>("/me/bio"),
  });
}
