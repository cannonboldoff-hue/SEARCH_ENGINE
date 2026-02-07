"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { PenLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BackLink } from "@/components/back-link";
import { SaveCardsModal } from "@/components/builder/save-cards-modal";
import { DraftCardFamily } from "@/components/builder/draft-card-family";
import { SavedCardFamily } from "@/components/builder/saved-card-family";
import { api } from "@/lib/api";
import {
  useExperienceCards,
  useExperienceCardFamilies,
  useCardMutations,
  useCardForms,
  EXPERIENCE_CARDS_QUERY_KEY,
  EXPERIENCE_CARD_FAMILIES_QUERY_KEY,
} from "@/hooks";
import type {
  CardFamilyV1Response,
  DraftSetV1Response,
  RewriteTextResponse,
  ExperienceCardV1,
  ExperienceCard,
  ExperienceCardChild,
} from "@/types";

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
  const [editingKind, setEditingKind] = useState<"parent" | "child" | null>(null);
  const [editingSavedCardId, setEditingSavedCardId] = useState<string | null>(null);
  const [editingSavedChildId, setEditingSavedChildId] = useState<string | null>(null);

  const { data: savedCards = [], isLoading: loadingCards } = useExperienceCards();
  const { data: savedFamilies = [], isLoading: loadingFamilies } = useExperienceCardFamilies();

  const {
    editForm,
    setEditForm,
    childEditForm,
    setChildEditForm,
    populateParentForm,
    populateChildForm,
  } = useCardForms();

  const {
    hideCardMutation,
    patchCardMutation,
    patchChildMutation,
    hideChildMutation,
  } = useCardMutations(
    setCardFamilies,
    setEditingCardId,
    setEditingKind,
    setEditingSavedCardId,
    setEditingSavedChildId
  );

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

  const startEditingCard = useCallback(
    (card: ExperienceCardV1) => {
      const id = card.id ?? "";
      if (!id) return;
      setEditingCardId(id);
      setEditingKind("parent");
      setEditingSavedCardId(null);
      populateParentForm(card);
    },
    [populateParentForm]
  );

  const startEditingSavedCard = useCallback(
    (card: ExperienceCard) => {
      setEditingSavedCardId(card.id);
      setEditingCardId(null);
      setEditingKind(null);
      populateParentForm(card);
    },
    [populateParentForm]
  );

  const startEditingChild = useCallback(
    (child: ExperienceCardChild | (Record<string, unknown> & { id?: string })) => {
      const id = (child as { id?: string }).id ?? "";
      if (!id) return;
      setEditingSavedChildId(null);
      setEditingCardId(id);
      setEditingKind("child");
      populateChildForm(child);
    },
    [populateChildForm]
  );

  const startEditingSavedChild = useCallback(
    (child: ExperienceCardChild) => {
      setEditingCardId(null);
      setEditingKind(null);
      setEditingSavedChildId(child.id);
      populateChildForm(child);
    },
    [populateChildForm]
  );

  const submitEditCard = useCallback(() => {
    const cardId = editingSavedCardId ?? (editingKind === "parent" ? editingCardId : null);
    if (!cardId) return;
    const toNull = (s: string) => (s.trim() ? s.trim() : null);
    const intentSecondary = editForm.intent_secondary_str
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const confNum = editForm.confidence_score.trim() ? Number(editForm.confidence_score) : null;
    patchCardMutation.mutate({
      cardId,
      body: {
        title: toNull(editForm.title),
        summary: toNull(editForm.summary),
        normalized_role: toNull(editForm.normalized_role),
        domain: toNull(editForm.domain),
        sub_domain: toNull(editForm.sub_domain),
        company_name: toNull(editForm.company_name),
        company_type: toNull(editForm.company_type),
        location: toNull(editForm.location),
        employment_type: toNull(editForm.employment_type),
        start_date: toNull(editForm.start_date),
        end_date: toNull(editForm.end_date),
        is_current: editForm.is_current,
        intent_primary: toNull(editForm.intent_primary),
        intent_secondary: intentSecondary.length ? intentSecondary : null,
        seniority_level: toNull(editForm.seniority_level),
        confidence_score: confNum != null && !Number.isNaN(confNum) ? confNum : null,
        visibility: editForm.visibility,
      },
    });
  }, [editingCardId, editingKind, editingSavedCardId, editForm, patchCardMutation]);

  const submitEditChild = useCallback(() => {
    const childId = editingSavedChildId ?? (editingKind === "child" ? editingCardId : null);
    if (!childId) return;
    const tags = childEditForm.tagsStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    patchChildMutation.mutate({
      childId,
      body: {
        title: childEditForm.title.trim(),
        summary: childEditForm.summary.trim(),
        tags,
        time_range: childEditForm.time_range.trim(),
        company: childEditForm.company.trim(),
        location: childEditForm.location.trim(),
      },
    });
  }, [childEditForm, editingCardId, editingKind, editingSavedChildId, patchChildMutation]);

  const handleDeleteCard = useCallback(() => {
    if (!editingCardId) return;
    if (editingKind === "child") {
      hideChildMutation.mutate(editingCardId);
      return;
    }
    hideCardMutation.mutate(editingCardId);
  }, [editingCardId, editingKind, hideCardMutation, hideChildMutation]);

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    try {
      setSaveModalOpen(false);
      setDraftSetId(null);
      setCardFamilies(null);
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
      router.push("/home");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save cards");
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
    } finally {
      setIsSavingAll(false);
    }
  }, [draftSetId, queryClient, router]);

  const hasV1Families = (cardFamilies?.length ?? 0) > 0;
  const hasCards = hasV1Families || (draftSetId == null && savedFamilies.length > 0);

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
            {(loadingCards || loadingFamilies) && savedFamilies.length === 0 && !hasV1Families ? (
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
                  {cardFamilies?.map((family) => (
                    <DraftCardFamily
                      key={family.parent?.id ?? ""}
                      family={family}
                      editingCardId={editingCardId}
                      editingKind={editingKind}
                      editForm={editForm}
                      childEditForm={childEditForm}
                      onEditFormChange={(updates) => setEditForm((f) => ({ ...f, ...updates }))}
                      onChildEditFormChange={(updates) => setChildEditForm((f) => ({ ...f, ...updates }))}
                      onStartEditingCard={startEditingCard}
                      onStartEditingChild={startEditingChild}
                      onSubmitEditCard={submitEditCard}
                      onSubmitEditChild={submitEditChild}
                      onDeleteCard={handleDeleteCard}
                      isCardSubmitting={patchCardMutation.isPending}
                      isCardDeleting={hideCardMutation.isPending}
                      isChildSubmitting={patchChildMutation.isPending}
                      isChildDeleting={hideChildMutation.isPending}
                    />
                  ))}
                </AnimatePresence>
                {draftSetId == null && savedFamilies.length > 0 && (
                  <motion.div
                    className="mt-4 pt-4 border-t border-border/50 space-y-3"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    <p className="text-xs font-medium text-muted-foreground mb-2">Saved cards</p>
                    {savedFamilies.map((family) => (
                      <SavedCardFamily
                        key={family.parent.id}
                        parent={family.parent}
                        children={family.children}
                        deletedId={deletedId}
                        editingSavedCardId={editingSavedCardId}
                        editingSavedChildId={editingSavedChildId}
                        editForm={editForm}
                        childEditForm={childEditForm}
                        onEditFormChange={(updates) => setEditForm((f) => ({ ...f, ...updates }))}
                        onChildEditFormChange={(updates) => setChildEditForm((f) => ({ ...f, ...updates }))}
                        onStartEditing={startEditingSavedCard}
                        onStartEditingChild={startEditingSavedChild}
                        onCancelEditing={() => setEditingSavedCardId(null)}
                        onCancelEditingChild={() => setEditingSavedChildId(null)}
                        onSubmitEdit={submitEditCard}
                        onSubmitEditChild={submitEditChild}
                        onDelete={(id) => {
                          setDeletedId(id);
                          hideCardMutation.mutate(id);
                          setTimeout(() => setDeletedId(null), 5000);
                        }}
                        onDeleteChild={(id) => {
                          setDeletedId(id);
                          hideChildMutation.mutate(id);
                          setTimeout(() => setDeletedId(null), 5000);
                        }}
                        isSubmitting={patchCardMutation.isPending || patchChildMutation.isPending}
                      />
                    ))}
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
