"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { debounce } from "lodash";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardFooter } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type DraftCard = {
  draft_card_id: string;
  title: string | null;
  context: string | null;
  constraints: string | null;
  decisions: string | null;
  outcome: string | null;
  tags: string[];
  company: string | null;
  team: string | null;
  role_title: string | null;
  time_range: string | null;
  source_span: string | null;
};

type DraftSet = {
  draft_set_id: string;
  raw_experience_id: string;
  cards: DraftCard[];
};

type ExperienceCard = {
  id: string;
  person_id: string;
  raw_experience_id: string | null;
  status: string;
  title: string | null;
  context: string | null;
  constraints: string | null;
  decisions: string | null;
  outcome: string | null;
  tags: string[];
  company: string | null;
  team: string | null;
  role_title: string | null;
  time_range: string | null;
  created_at: string | null;
  updated_at: string | null;
};

const CARD_FIELDS = [
  "title",
  "context",
  "constraints",
  "decisions",
  "outcome",
  "tags",
  "company",
  "team",
  "role_title",
  "time_range",
] as const;

export default function BuilderPage() {
  const [rawText, setRawText] = useState("");
  const [draftCards, setDraftCards] = useState<DraftCard[]>([]);
  const [rawExperienceId, setRawExperienceId] = useState<string | null>(null);
  const [draftSetId, setDraftSetId] = useState<string | null>(null);
  const [editedFields, setEditedFields] = useState<Record<string, Record<string, string | string[]>>>({});
  const [searchWithinCards, setSearchWithinCards] = useState("");
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  const extractAbortRef = useRef<AbortController | null>(null);
  const prevDraftCardsRef = useRef<DraftCard[]>([]);

  const { data: savedCards = [], isLoading: loadingCards } = useQuery({
    queryKey: ["experience-cards"],
    queryFn: () => api<ExperienceCard[]>("/me/experience-cards"),
  });

  const extractDraft = useCallback(async (text: string) => {
    if (!text.trim()) {
      setDraftCards([]);
      setRawExperienceId(null);
      setDraftSetId(null);
      return;
    }
    extractAbortRef.current?.abort();
    extractAbortRef.current = new AbortController();
    try {
      const result = await api<DraftSet>("/experience-cards/draft", {
        method: "POST",
        body: { raw_text: text },
      });
      setRawExperienceId(result.raw_experience_id);
      setDraftSetId(result.draft_set_id);
      const prev = prevDraftCardsRef.current;
      const nextCards = result.cards;
      setEditedFields((prevEdits) => {
        const nextEdits: Record<string, Record<string, string | string[]>> = {};
        for (let i = 0; i < nextCards.length; i++) {
          const oldCard = prev[i];
          const newCard = nextCards[i];
          if (oldCard && prevEdits[oldCard.draft_card_id]) {
            nextEdits[newCard.draft_card_id] = prevEdits[oldCard.draft_card_id];
          }
        }
        return { ...prevEdits, ...nextEdits };
      });
      setDraftCards(nextCards);
      prevDraftCardsRef.current = nextCards;
    } catch (e) {
      console.error("Extract failed", e);
    }
  }, []);

  const debouncedExtract = useRef(
    debounce((text: string) => extractDraft(text), 800)
  ).current;

  useEffect(() => {
    debouncedExtract(rawText);
    return () => debouncedExtract.cancel();
  }, [rawText, debouncedExtract]);

  const mergeCardWithEdits = useCallback(
    (card: DraftCard): DraftCard => {
      const edits = editedFields[card.draft_card_id];
      if (!edits) return card;
      return {
        ...card,
        ...Object.fromEntries(
          Object.entries(edits).map(([k, v]) => [
            k,
            k === "tags" ? (Array.isArray(v) ? v : []) : v ?? (card as Record<string, unknown>)[k],
          ])
        ),
      } as DraftCard;
    },
    [editedFields]
  );

  const setFieldEdit = useCallback(
    (draftCardId: string, field: string, value: string | string[]) => {
      setEditedFields((prev) => ({
        ...prev,
        [draftCardId]: {
          ...(prev[draftCardId] || {}),
          [field]: value,
        },
      }));
    },
    []
  );

  const replaceWithAI = useCallback((draftCardId: string, card: DraftCard) => {
    setEditedFields((prev) => {
      const next = { ...prev };
      delete next[draftCardId];
      return next;
    });
    setDraftCards((prev) =>
      prev.map((c) => (c.draft_card_id === draftCardId ? card : c))
    );
  }, []);

  const createCardMutation = useMutation({
    mutationFn: (payload: {
      raw_experience_id?: string;
      title?: string;
      context?: string;
      constraints?: string;
      decisions?: string;
      outcome?: string;
      tags?: string[];
      company?: string;
      team?: string;
      role_title?: string;
      time_range?: string;
    }) => api<ExperienceCard>("/experience-cards", { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["experience-cards"] }),
  });

  const patchCardMutation = useMutation({
    mutationFn: ({ cardId, body }: { cardId: string; body: Record<string, unknown> }) =>
      api<ExperienceCard>(`/experience-cards/${cardId}`, { method: "PATCH", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["experience-cards"] }),
  });

  const approveCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<ExperienceCard>(`/experience-cards/${cardId}/approve`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["experience-cards"] }),
  });

  const hideCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<ExperienceCard>(`/experience-cards/${cardId}/hide`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["experience-cards"] }),
  });

  const saveDraftCard = useCallback(
    (merged: DraftCard) => {
      createCardMutation.mutate({
        raw_experience_id: rawExperienceId || undefined,
        title: merged.title || undefined,
        context: merged.context || undefined,
        constraints: merged.constraints || undefined,
        decisions: merged.decisions || undefined,
        outcome: merged.outcome || undefined,
        tags: merged.tags,
        company: merged.company || undefined,
        team: merged.team || undefined,
        role_title: merged.role_title || undefined,
        time_range: merged.time_range || undefined,
      });
    },
    [rawExperienceId, createCardMutation]
  );

  const displayCards = draftCards
    .map(mergeCardWithEdits)
    .filter(
      (c) =>
        !searchWithinCards ||
        JSON.stringify(c).toLowerCase().includes(searchWithinCards.toLowerCase())
    );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Experience Builder</h1>
      <p className="text-muted-foreground">
        Type your experience in the left panel. We&apos;ll extract cards after you pause. Edit and approve on the right.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[500px]">
        {/* Left: raw paragraph */}
        <Card className="flex flex-col">
          <CardHeader>
            <Label>Raw experience (free-form)</Label>
          </CardHeader>
          <CardContent className="flex-1">
            <Textarea
              placeholder="Paste or type your experience. e.g. I worked at Razorpay in the backend team for 2 years. Also did a stint at Google on search..."
              className="min-h-[300px] resize-y"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </CardContent>
        </Card>

        {/* Right: extracted cards */}
        <Card className="flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <Label>Extracted cards</Label>
            <Input
              placeholder="Search within cards..."
              className="max-w-[200px]"
              value={searchWithinCards}
              onChange={(e) => setSearchWithinCards(e.target.value)}
            />
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto max-h-[500px] space-y-3">
            {loadingCards && savedCards.length === 0 ? (
              <div className="text-muted-foreground text-sm">Loading your cards…</div>
            ) : (
              <>
                <AnimatePresence mode="popLayout">
                  {displayCards.length === 0 ? (
                    <div className="text-muted-foreground text-sm py-4">
                      {rawText.trim()
                        ? "Waiting for extraction… or add more text."
                        : "Type in the left panel to extract experience cards."}
                    </div>
                  ) : (
                    displayCards.map((card) => {
                      const merged = mergeCardWithEdits(card);
                      const isExpanded = expandedCards.has(card.draft_card_id);
                      return (
                        <motion.div
                          key={card.draft_card_id}
                          layout
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="border rounded-lg p-3 space-y-2"
                        >
                          <div
                            className="flex items-center justify-between cursor-pointer"
                            onClick={() =>
                              setExpandedCards((prev) => {
                                const next = new Set(prev);
                                if (next.has(card.draft_card_id)) next.delete(card.draft_card_id);
                                else next.add(card.draft_card_id);
                                return next;
                              })
                            }
                          >
                            <span className="font-medium truncate">
                              {merged.title || merged.company || "Untitled"}
                            </span>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                replaceWithAI(card.draft_card_id, card);
                              }}
                            >
                              Replace with AI
                            </Button>
                          </div>
                          {isExpanded && (
                            <div className="space-y-2 pt-2 border-t">
                              {CARD_FIELDS.map((field) => (
                                <div key={field} className="grid grid-cols-[100px_1fr] gap-2 items-center">
                                  <Label className="text-xs capitalize">{field.replace(/_/g, " ")}</Label>
                                  {field === "tags" ? (
                                    <Input
                                      value={(merged.tags || []).join(", ")}
                                      onChange={(e) =>
                                        setFieldEdit(
                                          card.draft_card_id,
                                          "tags",
                                          e.target.value.split(",").map((s) => s.trim()).filter(Boolean)
                                        )
                                      }
                                      placeholder="tag1, tag2"
                                    />
                                  ) : (
                                    <Input
                                      value={(merged[field] as string) ?? ""}
                                      onChange={(e) =>
                                        setFieldEdit(card.draft_card_id, field, e.target.value)
                                      }
                                      placeholder={field}
                                    />
                                  )}
                                </div>
                              ))}
                              <div className="flex gap-2 pt-2">
                                <Button
                                  size="sm"
                                  onClick={() => saveDraftCard(merged)}
                                  disabled={createCardMutation.isPending}
                                >
                                  Save as draft
                                </Button>
                              </div>
                            </div>
                          )}
                        </motion.div>
                      );
                    })
                  )}
                </AnimatePresence>
              </>
            )}

            {savedCards.length > 0 && (
              <div className="mt-6 pt-4 border-t">
                <Label className="text-sm font-medium">Your saved cards</Label>
                <ul className="mt-2 space-y-2">
                  {savedCards.map((c) => (
                    <li key={c.id} className="flex items-center justify-between rounded border p-2">
                      <span className="truncate">{c.title || c.company || c.id}</span>
                      <div className="flex gap-1">
                        {c.status === "DRAFT" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => patchCardMutation.mutate({ cardId: c.id, body: {} })}
                          >
                            Save
                          </Button>
                        )}
                        {c.status === "DRAFT" && (
                          <Button
                            size="sm"
                            onClick={() => approveCardMutation.mutate(c.id)}
                            disabled={approveCardMutation.isPending}
                          >
                            Approve
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => hideCardMutation.mutate(c.id)}
                        >
                          Hide
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
