import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { TiltCard } from "@/components/tilt-card";
import { CardTypeIcon } from "@/components/builder/card-type-icon";
import { V1CardDetails, v1CardTopics } from "@/components/builder/v1-card-details";
import { ParentCardEditForm } from "@/components/builder/parent-card-edit-form";
import { ChildCardEditForm } from "@/components/builder/child-card-edit-form";
import { cn } from "@/lib/utils";
import type { CardFamilyV1Response, ExperienceCardV1 } from "@/types";
import type { ParentCardForm, ChildCardForm } from "@/hooks/use-card-forms";

interface DraftCardFamilyProps {
  family: CardFamilyV1Response;
  editingCardId: string | null;
  editingKind: "parent" | "child" | null;
  editForm: ParentCardForm;
  childEditForm: ChildCardForm;
  onEditFormChange: (updates: Partial<ParentCardForm>) => void;
  onChildEditFormChange: (updates: Partial<ChildCardForm>) => void;
  onStartEditingCard: (card: ExperienceCardV1) => void;
  onStartEditingChild: (child: ExperienceCardV1) => void;
  onSubmitEditCard: () => void;
  onSubmitEditChild: () => void;
  onDeleteCard: () => void;
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
  onDeleteCard,
  isCardSubmitting,
  isCardDeleting,
  isChildSubmitting,
  isChildDeleting,
}: DraftCardFamilyProps) {
  const parent = family.parent as ExperienceCardV1;
  const children = (family.children ?? []) as ExperienceCardV1[];
  const parentId = parent?.id ?? "";
  const tags = parent ? v1CardTopics(parent) : [];
  const isEditingParent = editingKind === "parent" && editingCardId === parentId;

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
      {/* ── Parent card ── */}
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
              <span className="font-semibold text-sm truncate text-foreground">
                {(parent as { title?: string })?.title || parent?.headline || "Untitled"}
              </span>
              {children.length > 0 && (
                <span className="text-xs text-muted-foreground flex-shrink-0 tabular-nums">
                  {children.length} thread{children.length !== 1 ? "s" : ""}
                </span>
              )}
            </span>
            {isEditingParent ? (
              <ParentCardEditForm
                form={editForm}
                onChange={onEditFormChange}
                onSubmit={onSubmitEditCard}
                onDelete={onDeleteCard}
                isSubmitting={isCardSubmitting}
                isDeleting={isCardDeleting}
                checkboxIdPrefix="edit-parent"
              />
            ) : (
              <Button
                size="sm"
                variant="ghost"
                className="flex-shrink-0 text-muted-foreground hover:text-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  onStartEditingCard(parent);
                }}
              >
                Edit
              </Button>
            )}
          </div>
          {!isEditingParent && (
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
              <V1CardDetails card={parent} summaryFullWidth />
            </>
          )}
        </div>
      </TiltCard>

      {/* ── Thread children ── */}
      {children.length > 0 && (
        <div className="relative pl-7 pt-0 mt-0">
          {/* Vertical thread line */}
          <span
            className="thread-line thread-line-animated top-0 bottom-3"
            aria-hidden
          />

          <ul className="relative space-y-0">
            {children.map((child, childIdx) => {
              const childId = child?.id ?? "";
              const childRelation = child?.relation_type ?? "";
              const childTitle = (child as { title?: string })?.title ?? child?.headline ?? "Untitled";
              const isEditingThisChild = editingKind === "child" && editingCardId === childId;

              return (
                <motion.li
                  key={childId || childTitle}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: childIdx * 0.06, duration: 0.2 }}
                  className="relative py-2 first:pt-3"
                >
                  {/* Thread node */}
                  <span
                    className={cn(
                      "thread-node thread-node-sm thread-node-animated",
                      "top-1/2 -translate-y-1/2",
                      isEditingThisChild && "thread-node-active"
                    )}
                    style={{ animationDelay: `${childIdx * 60 + 100}ms` }}
                    aria-hidden
                  />

                  {/* Child block */}
                  <div className="ml-5 rounded-lg border border-border/40 bg-accent/30 px-3 py-2.5 transition-colors hover:bg-accent/50">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        {childRelation && (
                          <span className="text-[10px] uppercase tracking-wide text-muted-foreground/70 mr-2">
                            {String(childRelation).replace(/_/g, " ")}
                          </span>
                        )}
                        <p className="font-medium text-sm text-foreground">{childTitle}</p>
                      </div>
                      {isEditingThisChild ? (
                        <ChildCardEditForm
                          form={childEditForm}
                          onChange={onChildEditFormChange}
                          onSubmit={onSubmitEditChild}
                          onDelete={onDeleteCard}
                          isSubmitting={isChildSubmitting}
                          isDeleting={isChildDeleting}
                        />
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="flex-shrink-0 text-muted-foreground hover:text-foreground h-7 px-2"
                          onClick={() => onStartEditingChild(child as any)}
                        >
                          Edit
                        </Button>
                      )}
                    </div>
                    {!isEditingThisChild && <V1CardDetails card={child as any} compact />}
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
