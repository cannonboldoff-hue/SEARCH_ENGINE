"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiBlob } from "@/lib/api";

/** Fetches profile photo with Bearer auth and returns blob URL. Use for current user (/me/bio/photo) or another person (/people/{id}/photo). */
export function useProfilePhoto(photoPath: string | null | undefined) {
  const { data: blobUrl, isLoading, error } = useQuery({
    queryKey: ["profile-photo", photoPath],
    queryFn: async () => {
      if (!photoPath) return null;
      const blob = await apiBlob(photoPath);
      return blob ? URL.createObjectURL(blob) : null;
    },
    enabled: !!photoPath,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [blobUrl]);

  return {
    blobUrl: error ? null : blobUrl,
    isLoading,
    hasPhoto: !!photoPath,
  };
}
