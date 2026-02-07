import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { EXPERIENCE_CARDS_QUERY_KEY, EXPERIENCE_CARD_FAMILIES_QUERY_KEY } from "@/hooks";
import type {
  ExperienceCard,
  ExperienceCardPatch,
  ExperienceCardChild,
  ExperienceCardChildPatch,
  CardFamilyV1Response,
} from "@/types";

export function useCardMutations(
  setCardFamilies: React.Dispatch<React.SetStateAction<CardFamilyV1Response[] | null>>,
  setEditingCardId: (id: string | null) => void,
  setEditingKind: (kind: "parent" | "child" | null) => void,
  setEditingSavedCardId: (id: string | null) => void,
  setEditingSavedChildId: (id: string | null) => void
) {
  const queryClient = useQueryClient();

  const hideCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<ExperienceCard>(`/experience-cards/${cardId}/hide`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
    },
  });

  const patchCardMutation = useMutation({
    mutationFn: ({ cardId, body }: { cardId: string; body: ExperienceCardPatch }) =>
      api<ExperienceCard>(`/experience-cards/${cardId}`, { method: "PATCH", body }),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      setEditingSavedCardId(null);
      const timeRange =
        updated.start_date || updated.end_date
          ? [updated.start_date, updated.end_date].filter(Boolean).join(" – ")
          : updated.is_current
            ? "Ongoing"
            : null;
      setCardFamilies((prev) => {
        const next =
          prev?.map((fam) => {
            if (fam.parent?.id === updated.id) {
              return {
                ...fam,
                parent: {
                  ...fam.parent,
                  title: updated.title ?? undefined,
                  headline: updated.title ?? fam.parent.headline,
                  context: updated.summary ?? undefined,
                  summary: updated.summary ?? fam.parent.summary,
                  role_title: updated.normalized_role ?? undefined,
                  company: updated.company_name ?? undefined,
                  location: updated.location ?? undefined,
                  domain: updated.domain ?? undefined,
                  sub_domain: updated.sub_domain ?? undefined,
                  company_type: updated.company_type ?? undefined,
                  employment_type: updated.employment_type ?? undefined,
                  intent_primary: updated.intent_primary ?? undefined,
                  intent_secondary: updated.intent_secondary ?? [],
                  seniority_level: updated.seniority_level ?? undefined,
                  confidence_score: updated.confidence_score ?? undefined,
                  visibility: updated.visibility,
                  ...(timeRange ? { time_range: timeRange } : {}),
                },
              };
            }
            return {
              ...fam,
              children: fam.children,
            };
          }) ?? prev;
        return next as CardFamilyV1Response[] | null;
      });
      setEditingCardId(null);
      setEditingKind(null);
    },
  });

  const patchChildMutation = useMutation({
    mutationFn: ({ childId, body }: { childId: string; body: ExperienceCardChildPatch }) =>
      api<ExperienceCardChild>(`/experience-card-children/${childId}`, { method: "PATCH", body }),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
      setEditingSavedChildId(null);
      setCardFamilies((prev) => {
        const next =
          prev?.map((fam) => ({
            ...fam,
            children:
              fam.children?.map((c) => (c.id === updated.id ? ({ ...(c as any), ...(updated as any) } as any) : c)) ??
              [],
          })) ?? prev;
        return next as CardFamilyV1Response[] | null;
      });
      setEditingCardId(null);
      setEditingKind(null);
    },
  });

  const hideChildMutation = useMutation({
    mutationFn: (childId: string) =>
      api<ExperienceCardChild>(`/experience-card-children/${childId}/hide`, { method: "POST" }),
    onSuccess: (_, childId) => {
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
      setEditingSavedChildId(null);
      setCardFamilies((prev) => {
        const next =
          prev?.map((fam) => ({
            ...fam,
            children: fam.children?.filter((c) => c.id !== childId) ?? [],
          })) ?? prev;
        return next as CardFamilyV1Response[] | null;
      });
      setEditingCardId(null);
      setEditingKind(null);
    },
  });

  return {
    hideCardMutation,
    patchCardMutation,
    patchChildMutation,
    hideChildMutation,
  };
}
