import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { TiltCard } from "@/components/tilt-card";
import { CardTypeIcon } from "../card/card-type-icon";
import {
  CardDetails,
  cardTopics,
  displayCardTitle,
  getChildDisplayItems,
  isPlaceholderChildCard,
} from "../card/card-details";
import { ParentCardEditForm } from "../forms/parent-card-edit-form";
import { ChildCardEditForm } from "../forms/child-card-edit-form";
import { PenLine, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DraftCardFamily, ExperienceCard, ExperienceCardChild } from "@/types";
import type { ParentCardForm, ChildCardForm } from "@/hooks/use-card-forms";

interface DraftCardFamilyProps {
  family: DraftCardFamily;
  editingCardId: string | null;
  editingKind: "parent" | "child" | null;
  editForm: ParentCardForm;
  childEditForm: ChildCardForm;
  onEditFormChange: (updates: Partial<ParentCardForm>) => void;
  onChildEditFormChange: (updates: Partial<ChildCardForm>) => void;
  onStartEditingCard: (card: ExperienceCard | Record<string, unknown>) => void;
  onStartEditingChild: (child: ExperienceCardChild | Record<string, unknown>) => void;
  onSubmitEditCard: () => void;
  onSubmitEditChild: () => void;
  onDeleteParentCard: (id: string) => void;
  onDeleteChildCard: (id: string) => void;
  onUpdateParentFromMessyText?: (text: string) => Promise<void>;
  onUpdateChildFromMessyText?: (text: string) => Promise<void>;
  isUpdatingFromMessyText?: boolean;
  translateRawText?: (text: string) => Promise<string>;
  isCardSubmitting: boolean;
  isCardDeleting: boolean;
  isChildSubmitting: boolean;
  isChildDeleting: boolean;
}

export function DraftCardFamily({
  family,
  editingCardId,
  editingKind,
  editForm,
  childEditForm,
  onEditFormChange,
  onChildEditFormChange,
  onStartEditingCard,
  onStartEditingChild,
  onSubmitEditCard,
  onSubmitEditChild,
  onDeleteParentCard,
  onDeleteChildCard,
  onUpdateParentFromMessyText,
  onUpdateChildFromMessyText,
  isUpdatingFromMessyText = false,
  translateRawText,
  isCardSubmitting,
  isCardDeleting,
  isChildSubmitting,
  isChildDeleting,
}: DraftCardFamilyProps) {
  const parent = family.parent as ExperienceCard | Record<string, unknown>;
  const parentAny = parent as Record<string, unknown>;
  const allChildren = (family.children ?? []) as ExperienceCardChild[];
  const children = allChildren.filter((c) => !isPlaceholderChildCard(c));
  const parentId = String(parentAny?.id ?? parentAny?.card_id ?? "").trim();
  const tags = parent ? cardTopics(parent) : [];
  const isEditingParent = editingKind === "parent" && editingCardId === parentId;
  const parentRelationType = (parentAny?.relation_type ?? "").toString().trim();
  const relationDisplay = (rt: string) => (rt ? String(rt).replace(/_/g, " ").toUpperCase() : "");

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
      exit={{ opacity: 0, rotateX: 8, scale: 0.96 }}
      transition={{ type: "spring", stiffness: 280, damping: 26 }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      className="relative max-w-full min-w-0"
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
        <div className="p-4 sm:p-5 min-w-0">
          {parentRelationType && (
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
              {relationDisplay(parentRelationType)}
            </p>
          )}
          <div className="flex items-start justify-between gap-2 w-full min-w-0">
            <span className="flex items-center gap-2 min-w-0 flex-1 truncate">
                <span className="text-muted-foreground flex-shrink-0">
                  <CardTypeIcon tags={tags} title={displayCardTitle((parentAny?.title ?? parentAny?.headline) as string, "Untitled")} />
                </span>
                <span className="font-semibold text-sm truncate text-foreground">
                  {displayCardTitle((parentAny?.title ?? parentAny?.headline) as string, "Untitled")}
              </span>
              {children.length > 0 && (
                <span className="text-xs text-muted-foreground flex-shrink-0 tabular-nums">
                  {children.length} thread{children.length !== 1 ? "s" : ""}
                </span>
              )}
            </span>
            {isEditingParent ? (
              <span className="flex-shrink-0" />
            ) : (
              <div className="relative z-10 flex gap-0.5 flex-shrink-0" style={{ pointerEvents: "auto" }}>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                  onPointerDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onStartEditingCard(parent);
                  }}
                >
                  <PenLine className="h-3.5 w-3.5" />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-destructive h-7 w-7 p-0"
                  onPointerDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (parentId) onDeleteParentCard(parentId);
                  }}
                  disabled={isCardDeleting || !parentId}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </div>
          {isEditingParent ? (
            <ParentCardEditForm
              form={editForm}
              onChange={onEditFormChange}
              onSubmit={onSubmitEditCard}
              isSubmitting={isCardSubmitting}
              isDeleting={isCardDeleting}
              checkboxIdPrefix="edit-parent"
              showDeleteButton={false}
              onUpdateFromMessyText={onUpdateParentFromMessyText}
              isUpdatingFromMessyText={isUpdatingFromMessyText}
              translateRawText={translateRawText}
            />
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
              <CardDetails card={parent} summaryFullWidth />
            </>
          )}
        </div>
      </TiltCard>

      {children.length > 0 && (
        <div className="relative pl-7 pt-0 mt-0">
          <span
            className="thread-line thread-line-animated top-0 bottom-3"
            aria-hidden
          />
          <ul className="relative space-y-0">
            {children.map((child, childIdx) => {
              const childId = child?.id ?? "";
              const childRelationType = (child?.child_type ?? "").toString().trim();
              const isEditingThisChild = editingKind === "child" && editingCardId === childId;

              return (
                <motion.li
                  key={childId || childRelationType || childIdx}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: childIdx * 0.06, duration: 0.2 }}
                  className="relative py-2 first:pt-3"
                >
                  <span
                    className={cn(
                      "thread-node thread-node-sm thread-node-animated",
                      "top-1/2 -translate-y-1/2",
                      isEditingThisChild && "thread-node-active"
                    )}
                    style={{ animationDelay: `${childIdx * 60 + 100}ms` }}
                    aria-hidden
                  />
                  <div className="ml-5 rounded-lg border border-border/40 bg-accent/30 px-3 py-2.5 transition-colors hover:bg-accent/50">
                    {!isEditingThisChild && (
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          {childRelationType && (
                            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">
                              {relationDisplay(childRelationType)}
                            </p>
                          )}
                          <p className="font-medium text-sm text-foreground whitespace-pre-line">
                            {(() => {
                              const items = getChildDisplayItems(child as Record<string, unknown>);
                              const childType = childRelationType || "Untitled";
                              if (items.length === 0) return childType;
                              return items.map((it, i) => (
                                <span key={i}>
                                  {it.title && it.summary ? (
                                    <>
                                      {it.title}:{" "}
                                      <span style={{ color: "rgba(128, 128, 128, 0.6)" }}>{it.summary}</span>
                                    </>
                                  ) : (
                                    it.title || it.summary
                                  )}
                                  {i < items.length - 1 && "\n"}
                                </span>
                              ));
                            })()}
                          </p>
                        </div>
                        <div className="flex gap-0.5 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                            onClick={() => onStartEditingChild(child)}
                          >
                            <PenLine className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground hover:text-destructive h-7 w-7 p-0"
                            onClick={() => onDeleteChildCard(childId)}
                            disabled={isChildDeleting}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    )}
                    {isEditingThisChild ? (
                      <ChildCardEditForm
                        form={childEditForm}
                        onChange={onChildEditFormChange}
                        onSubmit={onSubmitEditChild}
                        isSubmitting={isChildSubmitting}
                        isDeleting={isChildDeleting}
                        showDeleteButton={false}
                        onUpdateFromMessyText={onUpdateChildFromMessyText}
                        isUpdatingFromMessyText={isUpdatingFromMessyText}
                      />
                    ) : (
                      <CardDetails card={child} compact />
                    )}
                  </div>
                </motion.li>
              );
            })}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
