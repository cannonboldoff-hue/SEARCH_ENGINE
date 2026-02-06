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
  ExperienceCardPatch,
  CardFamilyV1Response,
  DraftSetV1Response,
  RewriteTextResponse,
  ExperienceCardV1,
} from "@/types";

function v1CardTopics(card: ExperienceCardV1): string[] {
  return (card.topics ?? []).map((t) => (typeof t === "object" && t && "label" in t ? t.label : String(t)));
}

/** Renders ExperienceCardV1 fields that have values; empty fields are not shown. */
function V1CardDetails({ card, compact = false }: { card: ExperienceCardV1; compact?: boolean }) {
  if (!card) return null;
  const topicLabels = v1CardTopics(card);
  const timeObj = card?.time && typeof card.time === "object" ? card.time as { text?: string; start?: string; end?: string; ongoing?: boolean } : null;
  const timeText = timeObj?.text ?? (timeObj ? [timeObj.start, timeObj.end].filter(Boolean).join(" – ") || (timeObj.ongoing ? "Ongoing" : null) : null);
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
  const intent = card.intent != null && String(card.intent) !== "" ? String(card.intent).replace(/_/g, " ") : null;
  const rawText = (card.raw_text ?? "").trim();
  const lang = card.language && typeof card.language === "object" ? (card.language as { raw_text?: string; confidence?: string }).raw_text ?? (card.language as { confidence?: string }).confidence : null;
  const langStr = (lang ?? "").toString().trim() || null;
  const privacy = card.privacy && typeof card.privacy === "object" ? `${(card.privacy as { visibility?: string }).visibility ?? ""}${(card.privacy as { sensitive?: boolean }).sensitive ? ", sensitive" : ""}`.trim() || null : null;
  const quality = card.quality && typeof card.quality === "object"
    ? [`confidence: ${(card.quality as { overall_confidence?: string }).overall_confidence}`, `claim: ${(card.quality as { claim_state?: string }).claim_state}`, (card.quality as { needs_clarification?: boolean }).needs_clarification ? "needs clarification" : "", (card.quality as { clarifying_question?: string | null }).clarifying_question ?? ""].filter(Boolean).join("; ").trim() || null
    : null;
  const indexPhrases = (card.index?.search_phrases ?? []).length ? (card.index?.search_phrases ?? []).join(", ") : null;
  const indexRef = (card.index?.embedding_ref ?? "").trim() || null;

  const labelClass = compact ? "text-[10px] uppercase tracking-wide text-muted-foreground" : "text-xs font-medium text-muted-foreground";
  const valueClass = compact ? "text-xs" : "text-sm";

  function Row({ label, value }: { label: string; value: React.ReactNode }) {
    if (value == null || value === "") return null;
    return (
      <div className="min-w-0">
        <span className={labelClass}>{label}</span>
        <p className={cn(valueClass, "break-words")}>{value}</p>
      </div>
    );
  }

  const toolingValue =
    tools.length || processes.length || (card.tooling?.raw ?? "").trim()
      ? [...tools, ...processes].filter(Boolean).join(", ") + ((card.tooling?.raw ?? "").trim() ? ` — ${card.tooling?.raw?.trim()}` : "")
      : null;
  const createdAt = (card.created_at ?? "").toString().trim() || null;
  const updatedAt = (card.updated_at ?? "").toString().trim() || null;
  const personId = (card.person_id ?? "").toString().trim() || null;
  const createdBy = (card.created_by ?? "").toString().trim() || null;

  const cardAny = card as Record<string, unknown>;
  const constraintsStr = (cardAny.constraints as string)?.trim() || null;
  const decisionsStr = (cardAny.decisions as string)?.trim() || null;
  const outcomeStr = (cardAny.outcome as string)?.trim() || null;
  const teamStr = (cardAny.team as string)?.trim() || null;
  const timeRangeStr = (cardAny.time_range as string)?.trim() || null;
  const roleTitleStr = (cardAny.role_title as string)?.trim() || null;
  const companyStr = (cardAny.company as string)?.trim() || null;

  const rows = [
    card.parent_id != null && card.parent_id !== "" && { label: "Parent ID", value: card.parent_id },
    card.depth != null && { label: "Depth", value: String(card.depth) },
    card.relation_type != null && card.relation_type !== "" && { label: "Relation type", value: String(card.relation_type).replace(/_/g, " ") },
    intent && { label: "Intent", value: intent },
    (timeText || timeRangeStr) && { label: "Time", value: timeText || timeRangeStr },
    roleTitleStr && { label: "Role", value: roleTitleStr },
    companyStr && { label: "Company", value: companyStr },
    teamStr && { label: "Team", value: teamStr },
    constraintsStr && { label: "Constraints", value: constraintsStr },
    decisionsStr && { label: "Decisions", value: decisionsStr },
    outcomeStr && { label: "Outcome", value: outcomeStr },
    langStr && { label: "Language", value: langStr },
    roles.length > 0 && { label: "Roles", value: roles.join(", ") },
    actions.length > 0 && { label: "Actions", value: actions.join(", ") },
    topicLabels.length > 0 && { label: "Topics", value: topicLabels.join(", ") },
    entities.length > 0 && { label: "Entities", value: entities.join(", ") },
    toolingValue && { label: "Tooling", value: toolingValue },
    outcomes.length > 0 && { label: "Outcomes", value: outcomes.join("; ") },
    evidence.length > 0 && { label: "Evidence", value: evidence.join("; ") },
    privacy && { label: "Privacy", value: privacy },
    quality && { label: "Quality", value: quality },
    indexPhrases && { label: "Search phrases", value: indexPhrases },
    indexRef && { label: "Embedding ref", value: indexRef },
    rawText && { label: "Raw text", value: rawText },
    createdAt && { label: "Created at", value: createdAt },
    updatedAt && { label: "Updated at", value: updatedAt },
    card.edited_at != null && card.edited_at !== "" && { label: "Edited at", value: card.edited_at },
    personId && { label: "Person ID", value: personId },
    createdBy && { label: "Created by", value: createdBy },
    card.version != null && { label: "Version", value: String(card.version) },
  ].filter((r): r is { label: string; value: string } =>
    typeof r === "object" && r !== null && "value" in r && r.value != null && r.value !== ""
  );

  if (rows.length === 0) return null;

  const totalChars = rows.reduce((sum, row) => sum + `${row.label}${row.value}`.length, 0);
  const useTwoColumnCompact = compact && rows.length <= 6 && totalChars <= 220;
  const useTwoColumnFull = !compact && rows.length <= 8 && totalChars <= 320;

  return (
    <div
      className={cn(
        compact
          ? useTwoColumnCompact
            ? "mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5"
            : "mt-2 space-y-1.5"
          : useTwoColumnFull
            ? "mt-3 pt-3 border-t border-border/40 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2"
            : "space-y-2 mt-3 pt-3 border-t border-border/40"
      )}
    >
      {rows.map((r, i) => (
        <Row key={`${r.label}-${i}`} label={r.label} value={r.value} />
      ))}
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

  const hideCardMutation = useMutation({
    mutationFn: (cardId: string) =>
      api<ExperienceCard>(`/experience-cards/${cardId}/hide`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY }),
  });

  const [editForm, setEditForm] = useState<{
    title: string;
    summary: string;
    normalized_role: string;
    company_name: string;
    location: string;
    start_date: string;
    end_date: string;
    is_current: boolean;
    visibility: boolean;
  }>({
    title: "",
    summary: "",
    normalized_role: "",
    company_name: "",
    location: "",
    start_date: "",
    end_date: "",
    is_current: false,
    visibility: true,
  });

  const patchCardMutation = useMutation({
    mutationFn: ({ cardId, body }: { cardId: string; body: ExperienceCardPatch }) =>
      api<ExperienceCard>(`/experience-cards/${cardId}`, { method: "PATCH", body }),
    onSuccess: (updated) => {
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
                  ...(timeRange ? { time_range: timeRange } : {}),
                },
              };
            }
            return {
              ...fam,
              // Note: children are `ExperienceCardChild` records and are not patchable via `/experience-cards/:id`.
              children: fam.children,
            };
          }) ?? prev;
        return next as CardFamilyV1Response[] | null;
      });
      setEditingCardId(null);
    },
  });

  const startEditingCard = useCallback(
    (card: ExperienceCardV1 | (Record<string, unknown> & { id?: string })) => {
      const id = (card as { id?: string }).id ?? "";
      if (!id) return;
      const c = card as Record<string, unknown>;
      const loc = c.location as unknown;
      const locationStr =
        typeof loc === "string"
          ? loc
          : (loc && typeof loc === "object" && "text" in (loc as Record<string, unknown>) ? String((loc as Record<string, unknown>).text ?? "") : "");
      setEditingCardId(id);
      setEditForm({
        title: (c.title as string) ?? (c.headline as string) ?? "",
        summary: (c.context as string) ?? (c.summary as string) ?? "",
        normalized_role: (c.normalized_role as string) ?? (c.role_title as string) ?? "",
        company_name: (c.company_name as string) ?? (c.company as string) ?? "",
        location: locationStr,
        start_date: (c.start_date as string) ?? "",
        end_date: (c.end_date as string) ?? "",
        is_current: (c.is_current as boolean) ?? false,
        visibility: (c.visibility as boolean) ?? true,
      });
    },
    []
  );

  const submitEditCard = useCallback(() => {
    if (!editingCardId) return;
    const toNull = (s: string) => (s.trim() ? s.trim() : null);
    patchCardMutation.mutate({
      cardId: editingCardId,
      body: {
        title: toNull(editForm.title),
        summary: toNull(editForm.summary),
        normalized_role: toNull(editForm.normalized_role),
        company_name: toNull(editForm.company_name),
        location: toNull(editForm.location),
        start_date: toNull(editForm.start_date),
        end_date: toNull(editForm.end_date),
        is_current: editForm.is_current,
        visibility: editForm.visibility,
      },
    });
  }, [editingCardId, editForm, patchCardMutation]);

  const handleDeleteCard = useCallback(() => {
    if (!editingCardId) return;
    hideCardMutation.mutate(editingCardId);
  }, [editingCardId, hideCardMutation]);

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    try {
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
  const hasCards = hasV1Families || (draftSetId == null && savedCards.length > 0);

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
      className="flex flex-col h-[calc(100vh-6.5rem)] overflow-hidden"
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
                {draftSetId != null ? (
                  <>
                    <p className="font-medium text-foreground">No experiences extracted</p>
                    <p className="text-sm mt-1">We couldn’t structure this into cards. Try adding more detail (e.g. role, company, duration) and click Update again.</p>
                  </>
                ) : (
                  <>
                    <p className="font-medium text-foreground">No cards yet</p>
                    <p className="text-sm mt-1">Write something on the left and click Update.</p>
                  </>
                )}
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
                      return (
                        <motion.div
                          key={parentId}
                          layout
                          initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
                          animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
                          exit={{ opacity: 0, rotateX: 8, scale: 0.96 }}
                          transition={{ type: "spring", stiffness: 280, damping: 26 }}
                          style={{ transformStyle: "preserve-3d", perspective: 800 }}
                          className="relative max-w-full min-w-0"
                        >
                          <div className="relative pl-6">
                            {children.length > 0 && (
                              <span className="absolute left-2 top-10 bottom-4 w-px bg-border/60" aria-hidden />
                            )}
                            <div className="relative">
                              <span className="absolute -left-6 top-6 h-2 w-2 rounded-full bg-primary/60 border border-primary/30" aria-hidden />
                              <TiltCard
                                disabled
                                maxTilt={6}
                                scale={1.01}
                                className={cn(
                                  "rounded-xl border border-border/50 glass overflow-hidden max-w-full min-w-0",
                                  "border-l-4 border-l-primary depth-shadow"
                                )}
                              >
                                <div className="p-4 sm:p-5">
                                  <div className="flex items-start justify-between gap-2 w-full">
                                <span className="flex items-center gap-2 min-w-0 flex-1">
                                  <span className="text-muted-foreground flex-shrink-0">
                                    <CardTypeIcon tags={tags} title={(parent as { title?: string })?.title ?? parent?.headline ?? null} />
                                  </span>
                                  <span className="font-semibold text-sm truncate">
                                    {(parent as { title?: string })?.title || parent?.headline || "Untitled"}
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
                                      disabled={hideCardMutation.isPending}
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
                                      value={editForm.summary}
                                      onChange={(e) => setEditForm((f) => ({ ...f, summary: e.target.value }))}
                                      placeholder="A short summary"
                                      rows={3}
                                      className="text-sm resize-y"
                                    />
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Start date</Label>
                                      <Input
                                        type="date"
                                        value={editForm.start_date}
                                        onChange={(e) => setEditForm((f) => ({ ...f, start_date: e.target.value }))}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">End date</Label>
                                      <Input
                                        type="date"
                                        value={editForm.end_date}
                                        onChange={(e) => setEditForm((f) => ({ ...f, end_date: e.target.value }))}
                                        className="text-sm"
                                      />
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <input
                                      type="checkbox"
                                      id="edit-is-current-parent"
                                      checked={editForm.is_current}
                                      onChange={(e) => setEditForm((f) => ({ ...f, is_current: e.target.checked }))}
                                      className="rounded border-border"
                                    />
                                    <Label htmlFor="edit-is-current-parent" className="text-xs cursor-pointer">Current / ongoing</Label>
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div className="space-y-1.5">
                                      <Label className="text-xs">Company</Label>
                                      <Input
                                        value={editForm.company_name}
                                        onChange={(e) => setEditForm((f) => ({ ...f, company_name: e.target.value }))}
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
                                  <div className="space-y-1.5">
                                    <Label className="text-xs">Role (normalized)</Label>
                                    <Input
                                      value={editForm.normalized_role}
                                      onChange={(e) => setEditForm((f) => ({ ...f, normalized_role: e.target.value }))}
                                      placeholder="e.g. Backend Engineer"
                                      className="text-sm"
                                    />
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <input
                                      type="checkbox"
                                      id="edit-visible-parent"
                                      checked={editForm.visibility}
                                      onChange={(e) => setEditForm((f) => ({ ...f, visibility: e.target.checked }))}
                                      className="rounded border-border"
                                    />
                                    <Label htmlFor="edit-visible-parent" className="text-xs cursor-pointer">Visible</Label>
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
                                  <V1CardDetails card={parent} />
                                </>
                              )}
                            </div>
                          </TiltCard>
                          {children.length > 0 && (
                            <span className="absolute -left-5 top-full mt-1 h-4 w-px bg-border/60" aria-hidden />
                          )}
                        </div>
                          {children.length > 0 && (
                            <div className="mt-4 space-y-2 min-w-0">
                              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Child cards</p>
                              <ul className="space-y-2">
                                {children.map((child) => {
                                  const childId = child?.id ?? "";
                                  const childRelation = child?.relation_type ?? "";
                                  const childTitle = (child as { title?: string })?.title ?? child?.headline ?? "Untitled";
                                  return (
                                    <li
                                      key={childId || childTitle}
                                      className="relative"
                                    >
                                      <span className="absolute -left-6 top-5 h-px w-6 bg-border/60" aria-hidden />
                                      <span className="absolute -left-6 top-5 h-2 w-2 rounded-full bg-muted-foreground/40 border border-border/60" aria-hidden />
                                      <div className="rounded-lg border border-border/40 bg-muted/30 p-3 sm:p-4 min-w-0">
                                        <div className="flex items-start justify-between gap-2">
                                          <div className="min-w-0 flex-1">
                                            {childRelation && (
                                              <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-2">
                                                {String(childRelation).replace(/_/g, " ")}
                                              </span>
                                            )}
                                            <p className="font-medium text-sm">{childTitle}</p>
                                          </div>
                                          {/* Child cards are persisted as ExperienceCardChild and are not patchable via `/experience-cards/:id`. */}
                                        </div>
                                        <V1CardDetails card={child} compact />
                                      </div>
                                    </li>
                                  );
                                })}
                              </ul>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    );
                    }) : null}
                </AnimatePresence>
                {draftSetId == null && savedCards.length > 0 && (
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
                            {c.title || c.company_name || "Untitled"}
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
