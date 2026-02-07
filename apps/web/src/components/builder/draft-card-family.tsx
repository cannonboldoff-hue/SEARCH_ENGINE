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
      <div className="relative">
        <div className="relative">
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
        </div>
        {children.length > 0 && (
          <>
            <span
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -bottom-6 h-6 w-px bg-border/60"
              aria-hidden
            />
            <span
              className="pointer-events-none absolute left-1/2 -translate-x-1/2 -bottom-1 h-2 w-2 rounded-full bg-primary/50 border border-primary/30"
              aria-hidden
            />
          </>
        )}
      </div>
      {children.length > 0 && (
        <div className="relative mt-8 min-w-0">
          <span
            className="pointer-events-none absolute left-1/2 -translate-x-1/2 -top-8 h-8 w-px bg-border/60"
            aria-hidden
          />
          <span
            className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-2 bottom-3 w-px bg-border/60"
            aria-hidden
          />

          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide text-center">
            Child cards
          </p>
          <ul className="space-y-3 mt-2">
            {children.map((child) => {
              const childId = child?.id ?? "";
              const childRelation = child?.relation_type ?? "";
              const childTitle = (child as { title?: string })?.title ?? child?.headline ?? "Untitled";
              const isEditingThisChild = editingKind === "child" && editingCardId === childId;
              return (
                <li key={childId || childTitle} className="relative">
                  <span
                    className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-4 h-2 w-2 rounded-full bg-muted-foreground/40 border border-border/60"
                    aria-hidden
                  />
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
                          className="flex-shrink-0 text-muted-foreground hover:text-foreground"
                          onClick={() => onStartEditingChild(child as any)}
                        >
                          Edit
                        </Button>
                      )}
                    </div>
                    {!isEditingThisChild && <V1CardDetails card={child as any} />}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
