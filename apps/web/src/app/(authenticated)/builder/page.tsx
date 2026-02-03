"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  Building2,
  Code2,
  FlaskConical,
  Pencil,
  Rocket,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DraftCard, DraftSet, ExperienceCard } from "@/types";

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

const LONG_TEXT_FIELDS = new Set(["context", "constraints", "decisions", "outcome"]);

function cardTypeIcon(tags: string[], title: string | null) {
  const t = (tags || []).map((x) => x.toLowerCase()).join(" ");
  const tit = (title || "").toLowerCase();
  if (tit.includes("research") || t.includes("research")) return <FlaskConical className="h-4 w-4 text-violet-400" />;
  if (tit.includes("startup") || t.includes("startup")) return <Rocket className="h-4 w-4 text-amber-400" />;
  if (tit.includes("quant") || t.includes("quant") || tit.includes("finance")) return <TrendingUp className="h-4 w-4 text-emerald-400" />;
  if (tit.includes("open-source") || t.includes("open-source") || t.includes("opensource")) return <Code2 className="h-4 w-4 text-blue-400" />;
  return <Building2 className="h-4 w-4 text-muted-foreground" />;
}

export default function BuilderPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [rawText, setRawText] = useState("");
  const [draftCards, setDraftCards] = useState<DraftCard[]>([]);
  const [rawExperienceId, setRawExperienceId] = useState<string | null>(null);
  const [editedFields, setEditedFields] = useState<Record<string, Record<string, string | string[]>>>({});
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const prevDraftCardsRef = useRef<DraftCard[]>([]);

  const { data: savedCards = [], isLoading: loadingCards } = useQuery({
    queryKey: ["experience-cards"],
    queryFn: () => api<ExperienceCard[]>("/me/experience-cards"),
  });

  const extractDraft = useCallback(async () => {
    if (!rawText.trim()) {
      setDraftCards([]);
      setRawExperienceId(null);
      return;
    }
    setIsUpdating(true);
    try {
      const result = await api<DraftSet>("/experience-cards/draft", {
        method: "POST",
        body: { raw_text: rawText },
      });
      setRawExperienceId(result.raw_experience_id);
      const prev = prevDraftCardsRef.current;
      const nextCards = result.cards;
      setEditedFields((prevEdits) => {
        const nextEdits: Record<string, Record<string, string | string[]>> = {};
        const currentIds = new Set(nextCards.map((c) => c.draft_card_id));
        for (let i = 0; i < nextCards.length; i++) {
          const oldCard = prev[i];
          const newCard = nextCards[i];
          if (oldCard && prevEdits[oldCard.draft_card_id]) {
            nextEdits[newCard.draft_card_id] = prevEdits[oldCard.draft_card_id];
          }
        }
        return Object.fromEntries(
          Object.entries(nextEdits).filter(([id]) => currentIds.has(id))
        );
      });
      setDraftCards(nextCards);
      setExpandedCards(new Set(nextCards.map((c) => c.draft_card_id)));
      prevDraftCardsRef.current = nextCards;
    } catch (e) {
      console.error("Extract failed", e);
    } finally {
      setIsUpdating(false);
    }
  }, [rawText]);

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

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    const mergedDrafts = draftCards.map(mergeCardWithEdits);
    try {
      await Promise.all(
        mergedDrafts.map((merged) =>
          createCardMutation.mutateAsync({
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
          })
        )
      );
      setSaveModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["experience-cards"] });
      router.push("/home");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save cards");
      queryClient.invalidateQueries({ queryKey: ["experience-cards"] });
    } finally {
      setIsSavingAll(false);
    }
  }, [draftCards, mergeCardWithEdits, rawExperienceId, createCardMutation, queryClient, router]);

  const displayDrafts = draftCards.map(mergeCardWithEdits);
  const hasCards = displayDrafts.length > 0 || savedCards.length > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <div className="mb-4">
        <Link
          href="/profile"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Back to profile
        </Link>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
        {/* Left: Raw input */}
        <div className="flex flex-col min-h-0 glass border-border/50 rounded-xl p-4">
          <h2 className="text-lg font-semibold mb-1">Raw experience</h2>
          <p className="text-sm text-muted-foreground mb-3">
            Write freely. Add one experience at a time or multiple. We&apos;ll structure it into cards.
          </p>
          <Textarea
            placeholder="Paste or type your experience. e.g. I worked at Razorpay in the backend team for 2 years..."
            className="min-h-[240px] resize-y flex-1 font-mono text-sm"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
          />
          <div className="mt-3 space-y-1">
            <Button
              onClick={extractDraft}
              disabled={!rawText.trim() || isUpdating}
            >
              {isUpdating ? "Structuring…" : "Update"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Update regenerates cards using your Bio context. Your manual edits on cards will be preserved.
            </p>
          </div>
        </div>

        {/* Right: Experience cards */}
        <div className="flex flex-col min-h-0 glass border-border/50 rounded-xl p-4 flex-1">
          <h2 className="text-lg font-semibold mb-3 flex-shrink-0">Experience cards</h2>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
            {loadingCards && savedCards.length === 0 && displayDrafts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <div className="h-12 w-12 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center mb-2" />
                <p className="text-sm">Loading…</p>
              </div>
            ) : !hasCards ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-center">
                <div className="h-12 w-12 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center mb-3" />
                <p className="font-medium text-foreground">No cards yet</p>
                <p className="text-sm mt-1">Write something on the left and click Update.</p>
              </div>
            ) : (
              <>
                {isUpdating && (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="h-32 rounded-xl bg-muted/50 animate-pulse border border-border/50"
                      />
                    ))}
                  </div>
                )}
                <AnimatePresence mode="popLayout">
                  {displayDrafts.map((card) => {
                    const isExpanded = expandedCards.has(card.draft_card_id) || editingCardId === card.draft_card_id;
                    const isEditing = editingCardId === card.draft_card_id;
                    return (
                      <motion.div
                        key={card.draft_card_id}
                        layout
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className={cn(
                          "rounded-xl border border-border/50 glass overflow-hidden hover-lift max-w-full min-w-0",
                          "border-l-4 border-l-primary"
                        )}
                      >
                        <div className="p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-muted-foreground flex-shrink-0">
                                {cardTypeIcon(card.tags, card.title)}
                              </span>
                              <h3 className="font-semibold text-sm truncate">
                                {card.title || card.company || "Untitled"}
                              </h3>
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => {
                                  setEditingCardId(isEditing ? null : card.draft_card_id);
                                  if (!expandedCards.has(card.draft_card_id)) setExpandedCards((s) => new Set(s).add(card.draft_card_id));
                                }}
                                title="Edit"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                          {(card.tags || []).length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {card.tags.slice(0, 5).map((t, i) => (
                                <span
                                  key={`${card.draft_card_id}-tag-${i}-${t}`}
                                  className="rounded-md bg-muted/80 px-2 py-0.5 text-xs text-muted-foreground"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}
                          {card.context && (
                            <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                              {card.context}
                            </p>
                          )}
                          {card.decisions && (
                            <ul className="text-xs text-muted-foreground mt-2 list-disc list-inside space-y-0.5">
                              {card.decisions.split("\n").filter(Boolean).slice(0, 3).map((line, i) => (
                                <li key={i}>{line.trim()}</li>
                              ))}
                            </ul>
                          )}
                          {card.outcome && (
                            <p className="text-xs text-muted-foreground mt-2 italic">
                              {card.outcome}
                            </p>
                          )}
                          <div className="text-xs text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-0">
                            {card.time_range && <span>{card.time_range}</span>}
                            {card.company && <span>{card.company}</span>}
                          </div>
                          {isExpanded && (
                            <div className="mt-4 pt-4 border-t border-border/50 space-y-3 min-w-0">
                              {CARD_FIELDS.map((field) => (
                                <div key={field} className="grid grid-cols-[100px_1fr] gap-2 items-start min-w-0">
                                  <Label className="text-xs capitalize pt-2">{field.replace(/_/g, " ")}</Label>
                                  <div className="min-w-0">
                                    {field === "tags" ? (
                                      <Input
                                        value={(card.tags || []).join(", ")}
                                        onChange={(e) =>
                                          setFieldEdit(
                                            card.draft_card_id,
                                            "tags",
                                            e.target.value.split(",").map((s) => s.trim()).filter(Boolean)
                                          )
                                        }
                                        placeholder="tag1, tag2"
                                        className="text-sm w-full max-w-full"
                                      />
                                    ) : LONG_TEXT_FIELDS.has(field) ? (
                                      <Textarea
                                        value={(card[field] as string) ?? ""}
                                        onChange={(e) =>
                                          setFieldEdit(card.draft_card_id, field, e.target.value)
                                        }
                                        placeholder={field}
                                        className="text-sm w-full max-w-full min-h-[80px] resize-y"
                                      />
                                    ) : (
                                      <Input
                                        value={(card[field] as string) ?? ""}
                                        onChange={(e) =>
                                          setFieldEdit(card.draft_card_id, field, e.target.value)
                                        }
                                        placeholder={field}
                                        className="text-sm w-full max-w-full"
                                      />
                                    )}
                                  </div>
                                </div>
                              ))}
                              <div className="flex gap-2 pt-1">
                                <Button size="sm" onClick={() => saveDraftCard(card)} disabled={createCardMutation.isPending}>
                                  Save
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => setEditingCardId(null)}>
                                  Done
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
                {savedCards.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-border/50">
                    <p className="text-xs font-medium text-muted-foreground mb-2">Saved cards</p>
                    <ul className="space-y-2">
                      {savedCards.map((c) => (
                        <li
                          key={c.id}
                          className={cn(
                            "flex items-center justify-between rounded-lg border border-border/50 p-3 bg-card",
                            deletedId === c.id && "opacity-50"
                          )}
                        >
                          <span className="text-sm truncate">{c.title || c.company || c.id}</span>
                          <div className="flex gap-1">
                            {c.status === "DRAFT" && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => approveCardMutation.mutate(c.id)}
                                disabled={approveCardMutation.isPending}
                              >
                                Approve
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-muted-foreground hover:text-destructive"
                              onClick={() => {
                                setDeletedId(c.id);
                                hideCardMutation.mutate(c.id);
                                setTimeout(() => setDeletedId(null), 5000);
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="flex-shrink-0 pt-4 pb-1 flex justify-end border-t border-border/50 mt-2">
            <Button onClick={() => setSaveModalOpen(true)} disabled={!hasCards}>
              Save Cards
            </Button>
          </div>
        </div>
      </div>

      {/* Save confirmation modal */}
      {saveModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setSaveModalOpen(false)}
        >
          <div
            className="rounded-xl glass border border-border p-6 max-w-md w-full mx-4 shadow-xl glow-ring"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold">Save experience cards?</h3>
            <p className="text-sm text-muted-foreground mt-2">
              This will update your searchable profile.
            </p>
            {saveError && (
              <div className="text-sm text-destructive bg-destructive/10 rounded-md p-3 mt-3">
                {saveError}
              </div>
            )}
            <div className="flex gap-2 mt-6 justify-end">
              <Button variant="outline" onClick={() => setSaveModalOpen(false)} disabled={isSavingAll}>
                Cancel
              </Button>
              <Button onClick={handleSaveCards} disabled={isSavingAll}>
                {isSavingAll ? "Saving…" : "Confirm Save"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
