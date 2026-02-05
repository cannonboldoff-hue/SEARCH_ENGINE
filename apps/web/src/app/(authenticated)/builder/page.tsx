"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BackLink } from "@/components/back-link";
import { TiltCard } from "@/components/tilt-card";
import { CardTypeIcon } from "@/components/builder/card-type-icon";
import { SaveCardsModal } from "@/components/builder/save-cards-modal";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useExperienceCards, EXPERIENCE_CARDS_QUERY_KEY } from "@/hooks";
import type {
  ExperienceCard,
  ExperienceCardCreate,
  CardFamilyV1Response,
  DraftSetV1Response,
  ExperienceCardV1,
} from "@/types";

function v1CardTopics(card: ExperienceCardV1): string[] {
  return (card.topics ?? []).map((t) => (typeof t === "object" && t && "label" in t ? t.label : String(t)));
}

/** Renders all filled ExperienceCardV1 fields so nothing is hidden. */
function V1CardDetails({ card, compact = false }: { card: ExperienceCardV1; compact?: boolean }) {
  if (!card) return null;
  const topicLabels = v1CardTopics(card);
  const timeText = card?.time && typeof card.time === "object" && "text" in card.time
    ? (card.time as { text?: string }).text
    : null;
  const locationText = card?.location && typeof card.location === "object" && "text" in card.location
    ? (card.location as { text?: string }).text
    : (card?.location && typeof card.location === "object" && "name" in card.location
      ? (card.location as { name?: string }).name
      : null);
  const roles = (card.roles ?? []).map((r) => typeof r === "object" && r && "label" in r ? (r as { label: string }).label : String(r));
  const actions = (card.actions ?? []).map((a) => typeof a === "object" && a && "verb" in a ? (a as { verb: string }).verb : String(a));
  const entities = (card.entities ?? []).map((e) => typeof e === "object" && e && "name" in e ? `${(e as { type?: string }).type ?? "entity"}: ${(e as { name: string }).name}` : String(e));
  const tools = (card.tooling?.tools ?? []).map((t) => typeof t === "object" && t && "name" in t ? (t as { name: string }).name : String(t));
  const processes = (card.tooling?.processes ?? []).map((p) => typeof p === "object" && p && "name" in p ? (p as { name: string }).name : String(p));
  const outcomes = (card.outcomes ?? []).map((o) => {
    if (typeof o !== "object" || !o) return null;
    const oo = o as { label?: string; value_text?: string | null; metric?: { name?: string | null; value?: number | null; unit?: string | null } };
    const parts = [oo.label, oo.value_text].filter(Boolean);
    if (oo.metric?.name != null || oo.metric?.value != null) {
      parts.push([oo.metric.name, oo.metric.value, oo.metric.unit].filter(Boolean).join(" "));
    }
    return parts.length ? parts.join(": ") : null;
  }).filter(Boolean) as string[];
  const evidence = (card.evidence ?? []).map((e) => {
    if (typeof e !== "object" || !e) return null;
    const ee = e as { type?: string; url?: string | null; note?: string | null };
    return [ee.type, ee.url ?? ee.note].filter(Boolean).join(": ");
  }).filter(Boolean) as string[];
  const intent = card.intent && String(card.intent) !== "other" && String(card.intent) !== "mixed" ? String(card.intent).replace(/_/g, " ") : null;

  const rawText = (card.raw_text ?? "").trim();
  const hasAny = intent || timeText || locationText || roles.length > 0 || actions.length > 0
    || topicLabels.length > 0 || entities.length > 0 || tools.length > 0 || processes.length > 0
    || outcomes.length > 0 || evidence.length > 0 || (card.tooling?.raw ?? "").trim() || rawText;

  if (!hasAny) return null;

  const labelClass = compact ? "text-[10px] uppercase tracking-wide text-muted-foreground" : "text-xs font-medium text-muted-foreground";
  const valueClass = compact ? "text-xs" : "text-sm";

  return (
    <div className={compact ? "space-y-1.5 mt-2" : "space-y-2 mt-3 pt-3 border-t border-border/40"}>
      {intent && (
        <div>
          <span className={labelClass}>Intent</span>
          <p className={valueClass}>{intent}</p>
        </div>
      )}
      {timeText && (
        <div>
          <span className={labelClass}>Time</span>
          <p className={valueClass}>{timeText}</p>
        </div>
      )}
      {locationText && (
        <div>
          <span className={labelClass}>Location</span>
          <p className={valueClass}>{locationText}</p>
        </div>
      )}
      {roles.length > 0 && (
        <div>
          <span className={labelClass}>Roles</span>
          <p className={valueClass}>{roles.join(", ")}</p>
        </div>
      )}
      {actions.length > 0 && (
        <div>
          <span className={labelClass}>Actions</span>
          <p className={valueClass}>{actions.join(", ")}</p>
        </div>
      )}
      {topicLabels.length > 0 && (
        <div>
          <span className={labelClass}>Topics</span>
          <p className={valueClass}>{topicLabels.join(", ")}</p>
        </div>
      )}
      {entities.length > 0 && (
        <div>
          <span className={labelClass}>Entities</span>
          <p className={valueClass}>{entities.join(", ")}</p>
        </div>
      )}
      {(tools.length > 0 || processes.length > 0 || (card.tooling?.raw ?? "").trim()) && (
        <div>
          <span className={labelClass}>Tooling</span>
          <p className={valueClass}>
            {[...tools, ...processes].filter(Boolean).join(", ")}
            {(card.tooling?.raw ?? "").trim() && (
              <span className="block mt-1 text-muted-foreground">{card.tooling?.raw?.trim()}</span>
            )}
          </p>
        </div>
      )}
      {outcomes.length > 0 && (
        <div>
          <span className={labelClass}>Outcomes</span>
          <p className={valueClass}>{outcomes.join("; ")}</p>
        </div>
      )}
      {evidence.length > 0 && (
        <div>
          <span className={labelClass}>Evidence</span>
          <p className={valueClass}>{evidence.join("; ")}</p>
        </div>
      )}
      {rawText && (
        <div>
          <span className={labelClass}>Raw text</span>
          <p className={cn(valueClass, "whitespace-pre-wrap")}>{rawText}</p>
        </div>
      )}
    </div>
  );
}

export default function BuilderPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [rawText, setRawText] = useState("");
  const [cardFamilies, setCardFamilies] = useState<CardFamilyV1Response[] | null>(null);
  const [expandedFamilies, setExpandedFamilies] = useState<Set<string>>(new Set());
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);

  const { data: savedCards = [], isLoading: loadingCards } = useExperienceCards();

  const extractDraftV1 = useCallback(async () => {
    if (!rawText.trim()) {
      setCardFamilies([]);
      return;
    }
    setIsUpdating(true);
    try {
      const result = await api<DraftSetV1Response>("/experience-cards/draft-v1", {
        method: "POST",
        body: { raw_text: rawText },
      });
      setCardFamilies(result.card_families ?? []);
      setExpandedFamilies(new Set((result.card_families ?? []).map((f) => f.parent?.id).filter(Boolean) as string[]));
    } catch (e) {
      console.error("Draft V1 failed", e);
    } finally {
      setIsUpdating(false);
    }
  }, [rawText]);

  const createCardMutation = useMutation({
    mutationFn: (payload: ExperienceCardCreate) =>
      api<ExperienceCard>("/experience-cards", { method: "POST", body: payload }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY }),
  });

  const hideCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<ExperienceCard>(`/experience-cards/${cardId}/hide`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY }),
  });

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    try {
      if (cardFamilies && cardFamilies.length > 0) {
        const allIds = cardFamilies.flatMap((f) => [
          ...(f.parent?.id ? [f.parent.id] : []),
          ...(f.children ?? []).map((c) => c.id).filter(Boolean),
        ]);
        await Promise.all(
          allIds.map((id) => api<ExperienceCard>(`/experience-cards/${id}/approve`, { method: "POST" }))
        );
      }
      setSaveModalOpen(false);
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      router.push("/home");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save cards");
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
    } finally {
      setIsSavingAll(false);
    }
  }, [cardFamilies, queryClient, router]);

  const hasV1Families = (cardFamilies?.length ?? 0) > 0;
  const hasCards = hasV1Families || savedCards.length > 0;

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
              onClick={extractDraftV1}
              disabled={!rawText.trim() || isUpdating}
            >
              {isUpdating ? "Structuring…" : "Update"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Extracts a parent card per experience and child cards (skills, outcomes, etc.).
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
            {loadingCards && savedCards.length === 0 && !hasV1Families ? (
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
                  {hasV1Families && cardFamilies ? cardFamilies.map((family) => {
                      const parent = family.parent as ExperienceCardV1;
                      const children = (family.children ?? []) as ExperienceCardV1[];
                      const parentId = parent?.id ?? "";
                      const isExpanded = expandedFamilies.has(parentId);
                      const tags = parent ? v1CardTopics(parent) : [];
                      const timeText = parent?.time && typeof parent.time === "object" && "text" in parent.time
                        ? (parent.time as { text?: string }).text
                        : null;
                      const roleLabel = parent?.roles?.[0] && typeof parent.roles[0] === "object" && "label" in parent.roles[0]
                        ? (parent.roles[0] as { label: string }).label
                        : null;
                      return (
                        <motion.div
                          key={parentId}
                          layout
                          initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
                          animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
                          exit={{ opacity: 0, rotateX: 8, scale: 0.96 }}
                          transition={{ type: "spring", stiffness: 280, damping: 26 }}
                          style={{ transformStyle: "preserve-3d", perspective: 800 }}
                          className="max-w-full min-w-0 space-y-2"
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
                                  setExpandedFamilies((s) => {
                                    const next = new Set(s);
                                    if (next.has(parentId)) next.delete(parentId);
                                    else next.add(parentId);
                                    return next;
                                  })
                                }
                              >
                                <span className="flex items-center gap-2 min-w-0">
                                  <span className="text-muted-foreground flex-shrink-0">
                                    <CardTypeIcon tags={tags} title={parent?.headline ?? null} />
                                  </span>
                                  <span className="font-semibold text-sm truncate">
                                    {parent?.headline || "Untitled"}
                                  </span>
                                  {children.length > 0 && (
                                    <span className="text-xs text-muted-foreground flex-shrink-0">
                                      +{children.length} child{children.length !== 1 ? "ren" : ""}
                                    </span>
                                  )}
                                </span>
                              </button>
                              {tags.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {tags.map((t, i) => (
                                    <span
                                      key={`${parentId}-tag-${i}-${t}`}
                                      className="rounded-md bg-muted/80 px-2 py-0.5 text-xs text-muted-foreground"
                                    >
                                      {t}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {parent?.summary && (
                                <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                                  {parent.summary}
                                </p>
                              )}
                              <div className="text-xs text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-0">
                                {timeText && <span>{timeText}</span>}
                                {roleLabel && <span>{roleLabel}</span>}
                              </div>
                              <V1CardDetails card={parent} />
                              <AnimatePresence>
                                {isExpanded && children.length > 0 && (
                                  <motion.div
                                    className="mt-4 pt-4 border-t border-border/50 space-y-3 min-w-0"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.2 }}
                                  >
                                    <p className="text-xs font-medium text-muted-foreground">Child cards</p>
                                    <ul className="space-y-2">
                                      {children.map((child) => {
                                        const childRelation = child?.relation_type ?? "";
                                        const childHeadline = child?.headline ?? "Untitled";
                                        const childSummary = child?.summary ?? "";
                                        return (
                                          <li
                                            key={child?.id ?? childHeadline}
                                            className="rounded-lg border border-border/40 bg-muted/30 p-3"
                                          >
                                            {childRelation && (
                                              <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-2">
                                                {String(childRelation).replace(/_/g, " ")}
                                              </span>
                                            )}
                                            <p className="font-medium text-sm">{childHeadline}</p>
                                            {childSummary && (
                                              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                                {childSummary}
                                              </p>
                                            )}
                                            <V1CardDetails card={child} compact />
                                          </li>
                                        );
                                      })}
                                    </ul>
                                  </motion.div>
                                )}
                              </AnimatePresence>
                            </div>
                          </TiltCard>
                        </motion.div>
                      );
                    }) : null}
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
              onClick={() => {
                setSaveError(null);
                setSaveModalOpen(true);
              }}
              disabled={!hasV1Families}
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
