"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Trash2, Check, PenLine } from "lucide-react";
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
import type {
  ExperienceCard,
  ExperienceCardCreate,
  ExperienceCardPatch,
  CardFamilyV1Response,
  DraftSetV1Response,
  RewriteTextResponse,
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
  const locationText =
    typeof card?.location === "string"
      ? card.location
      : card?.location && typeof card.location === "object" && "text" in card.location
        ? (card.location as { text?: string }).text
        : (card?.location && typeof card.location === "object" && "name" in card.location
          ? (card.location as { name?: string }).name
          : (card?.location && typeof card.location === "object" && "city" in card.location
            ? (card.location as { city?: string }).city
            : null));
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
  const [draftSetId, setDraftSetId] = useState<string | null>(null);
  const [cardFamilies, setCardFamilies] = useState<CardFamilyV1Response[] | null>(null);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isRewriting, setIsRewriting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);

  const { data: savedCards = [], isLoading: loadingCards } = useExperienceCards();

  const rewriteText = useCallback(async () => {
    if (!rawText.trim()) return;
    setIsRewriting(true);
    try {
      const result = await api<RewriteTextResponse>("/experiences/rewrite", {
        method: "POST",
        body: { raw_text: rawText },
      });
      if (result?.rewritten_text != null) setRawText(result.rewritten_text);
    } catch (e) {
      console.error("Rewrite failed", e);
    } finally {
      setIsRewriting(false);
    }
  }, [rawText]);

  const extractDraftV1 = useCallback(async () => {
    if (!rawText.trim()) {
      setDraftSetId(null);
      setCardFamilies([]);
      return;
    }
    setIsUpdating(true);
    try {
      const result = await api<DraftSetV1Response>("/experience-cards/draft-v1", {
        method: "POST",
        body: { raw_text: rawText },
      });
      setDraftSetId(result.draft_set_id ?? null);
      setCardFamilies(result.card_families ?? []);
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

  const [editForm, setEditForm] = useState<{
    title: string;
    context: string;
    tagsStr: string;
    time_range: string;
    role_title: string;
    company: string;
    location: string;
  }>({ title: "", context: "", tagsStr: "", time_range: "", role_title: "", company: "", location: "" });

  const deleteCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<void>(`/experience-cards/${cardId}`, { method: "DELETE" }),
    onSuccess: (_, cardId) => {
      setCardFamilies((prev) => {
        if (!prev) return prev;
        const next = prev
          .map((fam) => {
            if (fam.parent?.id === cardId) return null;
            if (fam.children?.some((c) => c.id === cardId)) {
              return { ...fam, children: fam.children?.filter((c) => c.id !== cardId) ?? [] };
            }
            return fam;
          })
          .filter((f): f is CardFamilyV1Response => f != null);
        return next.length ? next : null;
      });
      setEditingCardId(null);
    },
  });

  const patchCardMutation = useMutation({
    mutationFn: ({ cardId, body }: { cardId: string; body: ExperienceCardPatch }) =>
      api<ExperienceCard>(`/experience-cards/${cardId}`, { method: "PATCH", body }),
    onSuccess: (updated) => {
      const locObj =
        updated.location != null
          ? { city: updated.location, text: updated.location, region: null, country: null, confidence: "medium" as const }
          : undefined;
      setCardFamilies((prev) => {
        const next =
          prev?.map((fam) => {
            if (fam.parent?.id === updated.id) {
              return {
                ...fam,
                parent: {
                  ...fam.parent,
                  title: updated.title ?? undefined,
                  context: updated.context ?? undefined,
                  tags: updated.tags ?? [],
                  headline: updated.title ?? fam.parent.headline,
                  summary: updated.context ?? fam.parent.summary,
                  topics: (updated.tags ?? []).map((l) => ({ label: l })),
                  time_range: updated.time_range ?? undefined,
                  role_title: updated.role_title ?? undefined,
                  company: updated.company ?? undefined,
                  ...(locObj ? { location: locObj } : {}),
                },
              };
            }
            return {
              ...fam,
              children: fam.children?.map((c) =>
                c.id === updated.id
                  ? {
                      ...c,
                      title: updated.title ?? undefined,
                      context: updated.context ?? undefined,
                      tags: updated.tags ?? [],
                      headline: updated.title ?? c.headline,
                      summary: updated.context ?? c.summary,
                      topics: (updated.tags ?? []).map((l) => ({ label: l })),
                      time_range: updated.time_range ?? undefined,
                      role_title: updated.role_title ?? undefined,
                      company: updated.company ?? undefined,
                      ...(locObj ? { location: locObj } : {}),
                    }
                  : c
              ),
            };
          }) ?? prev;
        return next as CardFamilyV1Response[] | null;
      });
      setEditingCardId(null);
    },
  });

  const startEditingCard = useCallback(
    (card: ExperienceCardV1 | (Record<string, unknown> & { id?: string; title?: string; headline?: string; context?: string; summary?: string; tags?: string[]; time_range?: string; role_title?: string; company?: string; location?: string | { city?: string; text?: string } })) => {
      const id = (card as { id?: string }).id ?? "";
      if (!id) return;
      const tags = (card as { tags?: string[] }).tags ?? v1CardTopics(card as ExperienceCardV1);
      const loc = (card as { location?: string | { city?: string; text?: string } }).location;
      const locationStr =
        typeof loc === "string" ? loc : (loc && typeof loc === "object" && "city" in loc ? loc.city : (loc && typeof loc === "object" && "text" in loc ? loc.text : "")) ?? "";
      setEditingCardId(id);
      setEditForm({
        title: (card as { title?: string }).title ?? (card as { headline?: string }).headline ?? "",
        context: (card as { context?: string }).context ?? (card as { summary?: string }).summary ?? "",
        tagsStr: tags.join(", "),
        time_range: (card as { time_range?: string }).time_range ?? "",
        role_title: (card as { role_title?: string }).role_title ?? "",
        company: (card as { company?: string }).company ?? "",
        location: locationStr,
      });
    },
    []
  );

  const submitEditCard = useCallback(() => {
    if (!editingCardId) return;
    const tags = editForm.tagsStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    patchCardMutation.mutate({
      cardId: editingCardId,
      body: {
        title: editForm.title || null,
        context: editForm.context || null,
        tags,
        time_range: editForm.time_range || null,
        role_title: editForm.role_title || null,
        company: editForm.company || null,
        location: editForm.location || null,
      },
    });
  }, [editingCardId, editForm]);

  const handleDeleteCard = useCallback(() => {
    if (!editingCardId) return;
    deleteCardMutation.mutate(editingCardId);
  }, [editingCardId, deleteCardMutation]);

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    try {
      if (draftSetId) {
        await api<ExperienceCard[]>("/draft-sets/" + encodeURIComponent(draftSetId) + "/commit", {
          method: "POST",
          body: {},
        });
      }
      setSaveModalOpen(false);
      setDraftSetId(null);
      setCardFamilies(null);
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      router.push("/home");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save cards");
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
    } finally {
      setIsSavingAll(false);
    }
  }, [draftSetId, queryClient, router]);

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
          <div className="flex items-start justify-between gap-2 mb-1">
            <h2 className="text-lg font-semibold">Raw experience</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={rewriteText}
              disabled={!rawText.trim() || isRewriting}
              className="flex-shrink-0"
            >
              <PenLine className="h-4 w-4 mr-1.5" />
              {isRewriting ? "Rewriting…" : "Rewrite"}
            </Button>
          </div>
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
                      const tags = parent ? v1CardTopics(parent) : [];
                      const timeText = parent?.time && typeof parent.time === "object" && "text" in parent.time
                        ? (parent.time as { text?: string }).text
                        : null;
                      const roleLabel = parent?.roles?.[0] && typeof parent.roles[0] === "object" && "label" in parent.roles[0]
                        ? (parent.roles[0] as { label: string }).label
                        : null;
                      const parentLocation =
                        typeof parent?.location === "string"
                          ? parent.location
                          : (parent?.location && typeof parent.location === "object" && "city" in parent.location
                            ? (parent.location as { city?: string }).city
                            : (parent?.location && typeof parent.location === "object" && "text" in parent.location
                              ? (parent.location as { text?: string }).text
                              : null));
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
                              <div className="flex items-start justify-between gap-2 w-full">
                                <span className="flex items-center gap-2 min-w-0 flex-1">
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
                                {editingCardId === parentId ? (
                                  <div className="flex items-center gap-1 flex-shrink-0">
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                      onClick={handleDeleteCard}
                                      disabled={deleteCardMutation.isPending}
                                    >
                                      Delete
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="default"
                                      onClick={submitEditCard}
                                      disabled={patchCardMutation.isPending}
                                    >
                                      <Check className="h-4 w-4 mr-1" />
                                      Done
                                    </Button>
                                  </div>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="flex-shrink-0 text-muted-foreground hover:text-foreground"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      startEditingCard(parent);
                                    }}
                                  >
                                    Edit
                                  </Button>
                                )}
                              </div>
                              {editingCardId === parentId ? (
                                <div className="mt-3 space-y-3 pt-3 border-t border-border/50">
                                  <div className="space-y-1.5">
                                    <Label className="text-xs">Title</Label>
                                    <Input
                                      value={editForm.title}
                                      onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                                      placeholder="Card title"
                                      className="text-sm"
                                    />
                                  </div>
                                  <div className="space-y-1.5">
                                    <Label className="text-xs">Summary</Label>
                                    <Textarea
                                      value={editForm.context}
                                      onChange={(e) => setEditForm((f) => ({ ...f, context: e.target.value }))}
                                      placeholder="Context / summary"
                                      rows={3}
                                      className="text-sm resize-y"
                                    />
                                  </div>
                                  <div className="space-y-1.5">
                                    <Label className="text-xs">Tags (comma-separated)</Label>
                                    <Input
                                      value={editForm.tagsStr}
                                      onChange={(e) => setEditForm((f) => ({ ...f, tagsStr: e.target.value }))}
                                      placeholder="e.g. Python, API design"
                                      className="text-sm"
                                    />
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Time range</Label>
                                      <Input
                                        value={editForm.time_range}
                                        onChange={(e) => setEditForm((f) => ({ ...f, time_range: e.target.value }))}
                                        placeholder="e.g. 2020–2022"
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Role</Label>
                                      <Input
                                        value={editForm.role_title}
                                        onChange={(e) => setEditForm((f) => ({ ...f, role_title: e.target.value }))}
                                        placeholder="Role title"
                                        className="text-sm"
                                      />
                                    </div>
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Company</Label>
                                      <Input
                                        value={editForm.company}
                                        onChange={(e) => setEditForm((f) => ({ ...f, company: e.target.value }))}
                                        placeholder="Company"
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Location</Label>
                                      <Input
                                        value={editForm.location}
                                        onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))}
                                        placeholder="City / location"
                                        className="text-sm"
                                      />
                                    </div>
                                  </div>
                                </div>
                              ) : (
                                <>
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
                                    {parentLocation && <span>{parentLocation}</span>}
                                  </div>
                                  <V1CardDetails card={parent} />
                                </>
                              )}
                              {children.length > 0 && (
                                  <div className="mt-4 pt-4 border-t border-border/50 space-y-3 min-w-0">
                                    <p className="text-xs font-medium text-muted-foreground">Child cards</p>
                                    <ul className="space-y-2">
                                      {children.map((child) => {
                                        const childId = child?.id ?? "";
                                        const childRelation = child?.relation_type ?? "";
                                        const childHeadline = child?.headline ?? "Untitled";
                                        const childSummary = child?.summary ?? "";
                                        const isEditingChild = editingCardId === childId;
                                        return (
                                          <li
                                            key={childId || childHeadline}
                                            className="rounded-lg border border-border/40 bg-muted/30 p-3"
                                          >
                                            <div className="flex items-start justify-between gap-2">
                                              <div className="min-w-0 flex-1">
                                                {childRelation && (
                                                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-2">
                                                    {String(childRelation).replace(/_/g, " ")}
                                                  </span>
                                                )}
                                                {isEditingChild ? null : (
                                                  <>
                                                    <p className="font-medium text-sm">{childHeadline}</p>
                                                    {childSummary && (
                                                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                                        {childSummary}
                                                      </p>
                                                    )}
                                                  </>
                                                )}
                                              </div>
                                              {isEditingChild ? (
                                                <div className="flex items-center gap-1 flex-shrink-0">
                                                  <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                                    onClick={handleDeleteCard}
                                                    disabled={deleteCardMutation.isPending}
                                                  >
                                                    Delete
                                                  </Button>
                                                  <Button
                                                    size="sm"
                                                    variant="default"
                                                    onClick={submitEditCard}
                                                    disabled={patchCardMutation.isPending}
                                                  >
                                                    <Check className="h-4 w-4 mr-1" />
                                                    Done
                                                  </Button>
                                                </div>
                                              ) : (
                                                <Button
                                                  size="sm"
                                                  variant="ghost"
                                                  className="flex-shrink-0 text-muted-foreground hover:text-foreground"
                                                  onClick={() => startEditingCard(child)}
                                                >
                                                  Edit
                                                </Button>
                                              )}
                                            </div>
                                            {isEditingChild ? (
                                              <div className="mt-3 space-y-3 pt-3 border-t border-border/40">
                                                <div className="space-y-1.5">
                                                  <Label className="text-xs">Title</Label>
                                                  <Input
                                                    value={editForm.title}
                                                    onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                                                    placeholder="Card title"
                                                    className="text-sm"
                                                  />
                                                </div>
                                                <div className="space-y-1.5">
                                                  <Label className="text-xs">Summary</Label>
                                                  <Textarea
                                                    value={editForm.context}
                                                    onChange={(e) => setEditForm((f) => ({ ...f, context: e.target.value }))}
                                                    placeholder="Context / summary"
                                                    rows={2}
                                                    className="text-sm resize-y"
                                                  />
                                                </div>
                                                <div className="space-y-1.5">
                                                  <Label className="text-xs">Tags (comma-separated)</Label>
                                                  <Input
                                                    value={editForm.tagsStr}
                                                    onChange={(e) => setEditForm((f) => ({ ...f, tagsStr: e.target.value }))}
                                                    placeholder="e.g. Python, API"
                                                    className="text-sm"
                                                  />
                                                </div>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                  <div className="space-y-1.5">
                                                    <Label className="text-xs">Time range</Label>
                                                    <Input
                                                      value={editForm.time_range}
                                                      onChange={(e) => setEditForm((f) => ({ ...f, time_range: e.target.value }))}
                                                      className="text-sm"
                                                    />
                                                  </div>
                                                  <div className="space-y-1.5">
                                                    <Label className="text-xs">Role</Label>
                                                    <Input
                                                      value={editForm.role_title}
                                                      onChange={(e) => setEditForm((f) => ({ ...f, role_title: e.target.value }))}
                                                      className="text-sm"
                                                    />
                                                  </div>
                                                </div>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                  <div className="space-y-1.5">
                                                    <Label className="text-xs">Company</Label>
                                                    <Input
                                                      value={editForm.company}
                                                      onChange={(e) => setEditForm((f) => ({ ...f, company: e.target.value }))}
                                                      className="text-sm"
                                                    />
                                                  </div>
                                                  <div className="space-y-1.5">
                                                    <Label className="text-xs">Location</Label>
                                                    <Input
                                                      value={editForm.location}
                                                      onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))}
                                                      className="text-sm"
                                                    />
                                                  </div>
                                                </div>
                                              </div>
                                            ) : (
                                              <V1CardDetails card={child} compact />
                                            )}
                                          </li>
                                        );
                                      })}
                                    </ul>
                                  </div>
                              )}
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
                          <span className="text-sm truncate">
                            {c.title || c.company || c.location || c.id}
                            {c.location && (c.title || c.company) && (
                              <span className="text-muted-foreground"> · {c.location}</span>
                            )}
                          </span>
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
