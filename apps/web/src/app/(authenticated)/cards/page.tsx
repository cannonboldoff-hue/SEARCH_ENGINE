"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/back-link";
import { PageLoading } from "@/components/feedback";
import { SavedCardFamily } from "@/components/builder";
import { api } from "@/lib/api";
import {
  useExperienceCardFamilies,
  useCardForms,
  useCardMutations,
  EXPERIENCE_CARD_FAMILIES_QUERY_KEY,
} from "@/hooks";
import type {
  ExperienceCard,
  ExperienceCardChild,
  ExperienceCardPatch,
  ExperienceCardChildPatch,
} from "@/types";

function getParentId(parent: ExperienceCard | Record<string, unknown>): string {
  const p = parent as Record<string, unknown>;
  return String(p.id ?? p.card_id ?? "").trim();
}

function parentFormToPatch(form: {
  title: string;
  summary: string;
  normalized_role: string;
  domain: string;
  sub_domain: string;
  company_name: string;
  company_type: string;
  location: string;
  employment_type: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  intent_primary: string;
  intent_secondary_str: string;
  seniority_level: string;
  confidence_score: string;
  experience_card_visibility: boolean;
}): ExperienceCardPatch {
  const intentSecondary = form.intent_secondary_str
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const confidence =
    form.confidence_score.trim() === ""
      ? null
      : Number(form.confidence_score);
  return {
    title: form.title.trim() || null,
    summary: form.summary.trim() || null,
    normalized_role: form.normalized_role.trim() || null,
    domain: form.domain.trim() || null,
    sub_domain: form.sub_domain.trim() || null,
    company_name: form.company_name.trim() || null,
    company_type: form.company_type.trim() || null,
    location: form.location.trim() || null,
    employment_type: form.employment_type.trim() || null,
    start_date: form.start_date.trim() || null,
    end_date: form.end_date.trim() || null,
    is_current: form.is_current,
    intent_primary: form.intent_primary.trim() || null,
    intent_secondary: intentSecondary.length ? intentSecondary : null,
    seniority_level: form.seniority_level.trim() || null,
    confidence_score: confidence,
    experience_card_visibility: form.experience_card_visibility,
  };
}

function childFormToPatch(form: {
  title: string;
  summary: string;
  items: { subtitle: string; sub_summary?: string | null }[];
}): ExperienceCardChildPatch {
  // Encode title/summary into first item; backend derives headline from items[0].subtitle
  const rawItems = form.items
    .map((it) => ({
      subtitle: (it.subtitle ?? "").trim(),
      sub_summary: (it.sub_summary ?? "").trim() || null,
    }))
    .filter((it) => it.subtitle);
  const title = form.title.trim();
  const summary = form.summary.trim();
  const items =
    rawItems.length > 0
      ? rawItems.map((it, i) =>
          i === 0
            ? {
                subtitle: title || it.subtitle,
                sub_summary: summary || it.sub_summary,
              }
            : it
        )
      : title || summary
        ? [{ subtitle: title || "Untitled", sub_summary: summary || null }]
        : [];
  return { items };
}

type FillFromTextResponse = {
  filled?: Record<string, unknown>;
};

/** Parent form key set for overwrite merge (Update button: apply all filled, not only empty). */
const PARENT_FORM_KEYS = new Set([
  "title", "summary", "normalized_role", "domain", "sub_domain", "company_name", "company_type",
  "location", "employment_type", "start_date", "end_date", "is_current", "intent_primary",
  "intent_secondary_str", "seniority_level", "confidence_score", "experience_card_visibility",
]);

/** Build updates from API filled by overwriting all form keys present in filled (for Update button). */
function applyFilledToParentFormOverwrite(filled: Record<string, unknown>): Record<string, unknown> {
  const updates: Record<string, unknown> = {};
  for (const key of Object.keys(filled)) {
    if (PARENT_FORM_KEYS.has(key)) {
      const val = filled[key];
      if (val !== undefined && val !== null) updates[key] = val;
    }
  }
  if (Array.isArray(filled.intent_secondary) && filled.intent_secondary.length > 0) {
    updates.intent_secondary_str = (filled.intent_secondary as string[])
      .map((s) => String(s).trim())
      .filter(Boolean)
      .join(", ");
  }
  return updates;
}

function mergeFilledIntoParentForm(
  form: Record<string, unknown>,
  filled: Record<string, unknown>
): Record<string, unknown> {
  const updates: Record<string, unknown> = {};
  for (const key of Object.keys(filled)) {
    const cur = form[key];
    const val = filled[key];
    const isEmpty =
      cur === undefined ||
      cur === null ||
      (typeof cur === "string" && String(cur).trim() === "");
    const hasValue =
      val !== undefined &&
      val !== null &&
      (typeof val !== "string" || String(val).trim() !== "");
    if (isEmpty && hasValue) updates[key] = val;
  }
  if (Array.isArray(filled.intent_secondary) && filled.intent_secondary.length > 0) {
    const str = (filled.intent_secondary as string[]).map((s) => String(s).trim()).filter(Boolean).join(", ");
    if (str && (form.intent_secondary_str == null || String(form.intent_secondary_str).trim() === "")) {
      updates.intent_secondary_str = str;
    }
  }
  return updates;
}

function mergeFilledIntoChildForm(
  form: Record<string, unknown>,
  filled: Record<string, unknown>
): Record<string, unknown> {
  const updates: Record<string, unknown> = {};
  for (const key of Object.keys(filled)) {
    const cur = form[key];
    const val = filled[key];
    if (key === "items" && Array.isArray(val) && val.length > 0) {
      // Append new items from filled; items uses { subtitle, sub_summary } (or title/description from API)
      const curItems = (Array.isArray(cur) ? cur : []) as Array<Record<string, unknown>>;
      const existingSubtitles = new Set(
        curItems.map((it) => String(it?.subtitle ?? it?.title ?? "").trim()).filter(Boolean)
      );
      const toAppend: Array<{ subtitle: string; sub_summary: string | null }> = [];
      for (const it of val as Array<Record<string, unknown>>) {
        if (!it || typeof it !== "object") continue;
        const sub = String(it.subtitle ?? it.title ?? "").trim();
        const sum = (it.sub_summary ?? it.description ?? "") as string;
        const sumVal = typeof sum === "string" && sum.trim() ? sum.trim() : null;
        if (sub && !existingSubtitles.has(sub)) {
          toAppend.push({ subtitle: sub, sub_summary: sumVal });
          existingSubtitles.add(sub);
        }
      }
      if (toAppend.length > 0) {
        const merged = [
          ...curItems.map((it) => ({
            subtitle: String(it?.subtitle ?? it?.title ?? "").trim(),
            sub_summary: (it?.sub_summary ?? it?.description ?? null) as string | null,
          })),
          ...toAppend,
        ];
        updates.items = merged;
      }
      continue;
    }
    const isEmpty =
      cur === undefined ||
      cur === null ||
      (typeof cur === "string" && String(cur).trim() === "") ||
      (Array.isArray(cur) && cur.length === 0);
    const hasValue =
      val !== undefined &&
      val !== null &&
      (typeof val !== "string" || String(val).trim() !== "") &&
      (!Array.isArray(val) || val.length > 0);
    if (isEmpty && hasValue) updates[key] = val;
  }
  return updates;
}

export default function YourCardsPage() {
  const queryClient = useQueryClient();
  const { data: savedFamilies = [], isLoading } = useExperienceCardFamilies();
  const hasCards = savedFamilies.length > 0;

  const [editingSavedCardId, setEditingSavedCardId] = useState<string | null>(
    null
  );
  const [editingSavedChildId, setEditingSavedChildId] = useState<string | null>(
    null
  );
  const [isUpdatingFromMessyText, setIsUpdatingFromMessyText] = useState(false);

  const noop = useCallback(() => {}, []);
  const {
    editForm,
    setEditForm,
    childEditForm,
    setChildEditForm,
    populateParentForm,
    populateChildForm,
  } = useCardForms();

  const {
    patchCardMutation,
    patchChildMutation,
    deleteCardMutation,
    deleteChildMutation,
  } = useCardMutations(
    noop,
    noop,
    noop,
    setEditingSavedCardId,
    setEditingSavedChildId
  );

  const onUpdateParentFromMessyText = useCallback(
    async (text: string) => {
      if (!editingSavedCardId || !text.trim()) return;
      setIsUpdatingFromMessyText(true);
      try {
        const currentCard = editForm as unknown as Record<string, unknown>;
        const res = await api<FillFromTextResponse>("/experience-cards/fill-missing-from-text", {
          method: "POST",
          body: {
            raw_text: text.trim(),
            current_card: currentCard,
            card_type: "parent",
            card_id: editingSavedCardId,
          },
        });
        if (res.filled && Object.keys(res.filled).length > 0) {
          const updates = applyFilledToParentFormOverwrite(res.filled);
          if (Object.keys(updates).length > 0) {
            setEditForm((prev) => ({ ...prev, ...updates }));
          }
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
        }
      } finally {
        setIsUpdatingFromMessyText(false);
      }
    },
    [editingSavedCardId, editForm, queryClient]
  );

  const onUpdateChildFromMessyText = useCallback(
    async (text: string) => {
      if (!editingSavedChildId || !text.trim()) return;
      setIsUpdatingFromMessyText(true);
      try {
        const currentCard = childEditForm as unknown as Record<string, unknown>;
        const res = await api<FillFromTextResponse>("/experience-cards/fill-missing-from-text", {
          method: "POST",
          body: {
            raw_text: text.trim(),
            current_card: currentCard,
            card_type: "child",
            child_id: editingSavedChildId,
          },
        });
        if (res.filled && Object.keys(res.filled).length > 0) {
          const updates = mergeFilledIntoChildForm(currentCard, res.filled);
          if (Object.keys(updates).length > 0) {
            setChildEditForm((prev) => ({ ...prev, ...updates }));
          }
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
        }
      } finally {
        setIsUpdatingFromMessyText(false);
      }
    },
    [editingSavedChildId, childEditForm, queryClient]
  );

  const onStartEditing = useCallback(
    (card: ExperienceCard) => {
      const id = getParentId(card);
      setEditingSavedCardId(id);
      setEditingSavedChildId(null);
      populateParentForm(card as Record<string, unknown> & { id?: string });
    },
    [populateParentForm]
  );

  const onStartEditingChild = useCallback(
    (child: ExperienceCardChild) => {
      setEditingSavedChildId(child.id);
      setEditingSavedCardId(null);
      populateChildForm(child as Record<string, unknown> & { id?: string });
    },
    [populateChildForm]
  );

  const onCancelEditing = useCallback(() => {
    setEditingSavedCardId(null);
  }, []);

  const onCancelEditingChild = useCallback(() => {
    setEditingSavedChildId(null);
  }, []);

  const onSubmitEdit = useCallback(() => {
    if (!editingSavedCardId) return;
    const body = parentFormToPatch(editForm);
    patchCardMutation.mutate({ cardId: editingSavedCardId, body });
  }, [editingSavedCardId, editForm, patchCardMutation]);

  const onSubmitEditChild = useCallback(() => {
    if (!editingSavedChildId) return;
    const body = childFormToPatch(childEditForm);
    patchChildMutation.mutate({ childId: editingSavedChildId, body });
  }, [editingSavedChildId, childEditForm, patchChildMutation]);

  const onDelete = useCallback(
    (id: string) => {
      deleteCardMutation.mutate(id);
    },
    [deleteCardMutation]
  );

  const onDeleteChild = useCallback(
    (id: string) => {
      deleteChildMutation.mutate(id);
    },
    [deleteChildMutation]
  );

  const isSubmitting =
    patchCardMutation.isPending || patchChildMutation.isPending;

  if (isLoading) {
    return (
      <PageLoading
        message="Loading experience cards..."
        className="py-12 flex flex-col items-center justify-center gap-3"
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-3xl mx-auto space-y-8"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <BackLink href="/profile" className="flex-shrink-0" />
        <Link href="/builder">
          <Button variant="outline" size="sm" className="h-9 touch-manipulation rounded-full px-4">
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Add experience
          </Button>
        </Link>
      </div>

      {!hasCards ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className="flex flex-col items-center justify-center py-16 px-4 rounded-2xl border border-dashed border-border/50 gap-4"
        >
          <p className="text-sm text-muted-foreground text-center">
            No experience cards yet
          </p>
          <Link href="/builder">
            <Button size="sm" className="rounded-full px-5 h-9">
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              Add your first experience
            </Button>
          </Link>
        </motion.div>
      ) : (
        <section className="space-y-4">
          <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">
            Your experience
          </h2>
          <div className="space-y-4">
            {savedFamilies.map((family, i) => (
              <SavedCardFamily
                key={getParentId(family.parent) || `family-${i}`}
                parent={family.parent as ExperienceCard}
                children={family.children ?? []}
                deletedId={null}
                editingSavedCardId={editingSavedCardId}
                editingSavedChildId={editingSavedChildId}
                editForm={editForm}
                childEditForm={childEditForm}
                onEditFormChange={(updates) =>
                  setEditForm((prev) => ({ ...prev, ...updates }))
                }
                onChildEditFormChange={(updates) =>
                  setChildEditForm((prev) => ({ ...prev, ...updates }))
                }
                onStartEditing={onStartEditing}
                onStartEditingChild={onStartEditingChild}
                onCancelEditing={onCancelEditing}
                onCancelEditingChild={onCancelEditingChild}
                onSubmitEdit={onSubmitEdit}
                onSubmitEditChild={onSubmitEditChild}
                onDelete={onDelete}
                onDeleteChild={onDeleteChild}
                isSubmitting={isSubmitting}
                onUpdateParentFromMessyText={onUpdateParentFromMessyText}
                onUpdateChildFromMessyText={onUpdateChildFromMessyText}
                isUpdatingFromMessyText={isUpdatingFromMessyText}
              />
            ))}
          </div>
        </section>
      )}
    </motion.div>
  );
}
