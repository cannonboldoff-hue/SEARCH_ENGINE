"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BackLink } from "@/components/back-link";
import { TiltCard } from "@/components/tilt-card";
import { CardTypeIcon } from "@/components/builder/card-type-icon";
import { SaveCardsModal } from "@/components/builder/save-cards-modal";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useExperienceCards, EXPERIENCE_CARDS_QUERY_KEY } from "@/hooks";
import type { DraftCard, DraftSet, ExperienceCard, Intent } from "@/types";
import { INTENTS } from "@/types";

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

export default function BuilderPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [rawText, setRawText] = useState("");
  const [draftCards, setDraftCards] = useState<DraftCard[]>([]);
  const [rawExperienceId, setRawExperienceId] = useState<string | null>(null);
  const [editedFields, setEditedFields] = useState<Record<string, Record<string, string | string[]>>>({});
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const prevDraftCardsRef = useRef<DraftCard[]>([]);

  const { data: savedCards = [], isLoading: loadingCards } = useExperienceCards();

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
      intent?: Intent;
    }) => api<ExperienceCard>("/experience-cards", { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY }),
  });

  const hideCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<ExperienceCard>(`/experience-cards/${cardId}/hide`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY }),
  });

  const saveDraftCard = useCallback(
    (merged: DraftCard) => {
      const intent = editedFields[merged.draft_card_id]?.intent as Intent | undefined;
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
        ...(intent && INTENTS.includes(intent) ? { intent } : {}),
      });
    },
    [rawExperienceId, createCardMutation, editedFields]
  );

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    const mergedDrafts = draftCards.map(mergeCardWithEdits);
    try {
      const created = await Promise.all(
        mergedDrafts.map((merged) => {
          const intent = editedFields[merged.draft_card_id]?.intent as Intent | undefined;
          return createCardMutation.mutateAsync({
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
            ...(intent && INTENTS.includes(intent) ? { intent } : {}),
          });
        })
      );
      await Promise.all(
        created.map((card) =>
          api<ExperienceCard>(`/experience-cards/${card.id}/approve`, { method: "POST" })
        )
      );
      setSaveModalOpen(false);
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      router.push("/home");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save cards");
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
    } finally {
      setIsSavingAll(false);
    }
  }, [draftCards, mergeCardWithEdits, rawExperienceId, createCardMutation, queryClient, router, editedFields]);

  const displayDrafts = draftCards.map(mergeCardWithEdits);
  const hasCards = displayDrafts.length > 0 || savedCards.length > 0;

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.06, delayChildren: 0.05 },
    },
  };
  const panelVariants = {
    hidden: { opacity: 0, x: -12 },
    visible: { opacity: 1, x: 0 },
  };
  const panelVariantsRight = {
    hidden: { opacity: 0, x: 12 },
    visible: { opacity: 1, x: 0 },
  };

  return (
    <motion.div
      className="flex flex-col h-[calc(100vh-4rem)]"
      initial="hidden"
      animate="visible"
      variants={containerVariants}
    >
      <motion.div className="mb-4" variants={panelVariants}>
        <BackLink href="/profile" />
      </motion.div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
        {/* Left: Raw input */}
        <motion.div
          className="flex flex-col min-h-0 glass border-border/50 rounded-xl p-4 perspective-1000 transform-3d depth-shadow"
          variants={panelVariants}
          transition={{ type: "spring", stiffness: 200, damping: 24 }}
          style={{ transformStyle: "preserve-3d" }}
        >
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
        </motion.div>

        {/* Right: Experience cards */}
        <motion.div
          className="flex flex-col min-h-0 glass border-border/50 rounded-xl p-4 flex-1 perspective-1000 transform-3d depth-shadow"
          variants={panelVariantsRight}
          transition={{ type: "spring", stiffness: 200, damping: 24 }}
          style={{ transformStyle: "preserve-3d" }}
        >
          <h2 className="text-lg font-semibold mb-3 flex-shrink-0">Experience cards</h2>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
            {loadingCards && savedCards.length === 0 && displayDrafts.length === 0 ? (
              <motion.div
                className="flex flex-col items-center justify-center py-12 text-muted-foreground"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                <motion.div
                  className="h-12 w-12 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center mb-2"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                />
                <p className="text-sm">Loading…</p>
              </motion.div>
            ) : !hasCards ? (
              <motion.div
                className="flex flex-col items-center justify-center py-12 text-muted-foreground text-center"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.35 }}
              >
                <motion.div
                  className="h-12 w-12 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center mb-3"
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                <p className="font-medium text-foreground">No cards yet</p>
                <p className="text-sm mt-1">Write something on the left and click Update.</p>
              </motion.div>
            ) : (
              <>
                {isUpdating && (
                  <motion.div
                    className="space-y-2"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    {[1, 2, 3].map((i) => (
                      <motion.div
                        key={i}
                        className="h-32 rounded-xl bg-muted/50 border border-border/50"
                        initial={{ opacity: 0.4, x: -8 }}
                        animate={{ opacity: 0.7, x: 0 }}
                        transition={{ delay: i * 0.1, duration: 0.4, repeat: Infinity, repeatType: "reverse", repeatDelay: 0.2 }}
                      />
                    ))}
                  </motion.div>
                )}
                <AnimatePresence mode="popLayout">
                  {displayDrafts.map((card) => {
                    const isExpanded = expandedCards.has(card.draft_card_id);
                    return (
                      <motion.div
                        key={card.draft_card_id}
                        layout
                        initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
                        exit={{ opacity: 0, rotateX: 8, scale: 0.96 }}
                        transition={{ type: "spring", stiffness: 280, damping: 26 }}
                        style={{ transformStyle: "preserve-3d", perspective: 800 }}
                        className="max-w-full min-w-0"
                      >
                        <TiltCard
                          disabled
                          maxTilt={6}
                          scale={1.01}
                          className={cn(
                            "rounded-xl border border-border/50 glass overflow-hidden max-w-full min-w-0",
                            "border-l-4 border-l-primary depth-shadow"
                          )}
                        >
                        <div className="p-4">
                          <button
                            type="button"
                            className="flex items-start justify-between gap-2 w-full text-left"
                            onClick={() =>
                              setExpandedCards((s) => {
                                const next = new Set(s);
                                if (next.has(card.draft_card_id)) next.delete(card.draft_card_id);
                                else next.add(card.draft_card_id);
                                return next;
                              })
                            }
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-muted-foreground flex-shrink-0">
                                <CardTypeIcon tags={card.tags ?? []} title={card.title} />
                              </span>
                              <h3 className="font-semibold text-sm truncate">
                                {card.title || card.company || "Untitled"}
                              </h3>
                            </div>
                          </button>
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
                          <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              className="mt-4 pt-4 border-t border-border/50 space-y-3 min-w-0"
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0 }}
                              transition={{ duration: 0.2 }}
                            >
                              <div className="grid grid-cols-[100px_1fr] gap-2 items-start min-w-0">
                                <Label className="text-xs pt-2">Intent</Label>
                                <div className="min-w-0">
                                  <select
                                    value={(editedFields[card.draft_card_id]?.intent as string) ?? "other"}
                                    onChange={(e) =>
                                      setFieldEdit(card.draft_card_id, "intent", e.target.value as Intent)
                                    }
                                    className={cn(
                                      "rounded-md border border-input bg-background px-3 py-2 text-sm w-full max-w-full",
                                      "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                                    )}
                                  >
                                    {INTENTS.map((intent) => (
                                      <option key={intent} value={intent}>
                                        {intent.replace(/_/g, " ")}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              </div>
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
                              </div>
                            </motion.div>
                          )}
                          </AnimatePresence>
                        </div>
                        </TiltCard>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
                {savedCards.length > 0 && (
                  <motion.div
                    className="mt-4 pt-4 border-t border-border/50"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    <p className="text-xs font-medium text-muted-foreground mb-2">Saved cards</p>
                    <ul className="space-y-2">
                      {savedCards.map((c, idx) => (
                        <motion.li
                          key={c.id}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: idx * 0.05 }}
                          className={cn(
                            "flex items-center justify-between rounded-lg border border-border/50 p-3 bg-card",
                            deletedId === c.id && "opacity-50"
                          )}
                        >
                          <span className="text-sm truncate">{c.title || c.company || c.id}</span>
                          <div className="flex gap-1">
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
                        </motion.li>
                      ))}
                    </ul>
                  </motion.div>
                )}
              </>
            )}
          </div>
          <div className="flex-shrink-0 pt-4 pb-1 flex justify-end border-t border-border/50 mt-2">
            <Button
              onClick={() => setSaveModalOpen(true)}
              disabled={displayDrafts.length === 0}
            >
              Save Cards
            </Button>
          </div>
        </motion.div>
      </div>

      <SaveCardsModal
        open={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        onConfirm={handleSaveCards}
        isSaving={isSavingAll}
        error={saveError}
      />
    </motion.div>
  );
}
