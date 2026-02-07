import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { TiltCard } from "@/components/tilt-card";
import { ParentCardEditForm } from "@/components/builder/parent-card-edit-form";
import { ChildCardEditForm } from "@/components/builder/child-card-edit-form";
import { PenLine, Trash2, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ExperienceCard, ExperienceCardChild } from "@/types";
import type { ParentCardForm, ChildCardForm } from "@/hooks/use-card-forms";

interface SavedCardFamilyProps {
  parent: ExperienceCard;
  children: ExperienceCardChild[];
  deletedId: string | null;
  editingSavedCardId: string | null;
  editingSavedChildId: string | null;
  editForm: ParentCardForm;
  childEditForm: ChildCardForm;
  onEditFormChange: (updates: Partial<ParentCardForm>) => void;
  onChildEditFormChange: (updates: Partial<ChildCardForm>) => void;
  onStartEditing: (card: ExperienceCard) => void;
  onStartEditingChild: (child: ExperienceCardChild) => void;
  onCancelEditing: () => void;
  onCancelEditingChild: () => void;
  onSubmitEdit: () => void;
  onSubmitEditChild: () => void;
  onDelete: (id: string) => void;
  onDeleteChild: (id: string) => void;
  isSubmitting: boolean;
}

export function SavedCardFamily({
  parent,
  children,
  deletedId,
  editingSavedCardId,
  editingSavedChildId,
  editForm,
  childEditForm,
  onEditFormChange,
  onChildEditFormChange,
  onStartEditing,
  onStartEditingChild,
  onCancelEditing,
  onCancelEditingChild,
  onSubmitEdit,
  onSubmitEditChild,
  onDelete,
  onDeleteChild,
  isSubmitting,
}: SavedCardFamilyProps) {
  const isEditingParent = editingSavedCardId === parent.id;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 280, damping: 26 }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      className={cn("relative max-w-full min-w-0", deletedId === parent.id && "opacity-50")}
    >
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
                <span className="font-semibold text-sm truncate">
                  {parent.title || parent.company_name || "Untitled"}
                </span>
                {children.length > 0 && (
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    +{children.length} child{children.length !== 1 ? "ren" : ""}
                  </span>
                )}
              </span>
              {isEditingParent ? (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-muted-foreground"
                    onClick={onCancelEditing}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    variant="default"
                    onClick={onSubmitEdit}
                    disabled={isSubmitting}
                  >
                    <Check className="h-4 w-4 mr-1" />
                    Done
                  </Button>
                </div>
              ) : (
                <div className="flex gap-1 flex-shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={() => onStartEditing(parent)}
                  >
                    <PenLine className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(parent.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
            {isEditingParent ? (
              <ParentCardEditForm
                form={editForm}
                onChange={onEditFormChange}
                onSubmit={onSubmitEdit}
                onDelete={() => onDelete(parent.id)}
                isSubmitting={isSubmitting}
                checkboxIdPrefix={`edit-saved-${parent.id}`}
              />
            ) : (
              <div className="mt-3 pt-3 border-t border-border/40 space-y-1.5">
                {parent.summary && (
                  <p className="text-sm text-muted-foreground line-clamp-3">{parent.summary}</p>
                )}
                <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                  {parent.company_name && <span>{parent.company_name}</span>}
                  {parent.domain && <span>{parent.domain}</span>}
                  {parent.normalized_role && <span>{parent.normalized_role}</span>}
                </div>
              </div>
            )}
          </div>
        </TiltCard>
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
              const isEditingThisChild = editingSavedChildId === child.id;
              return (
                <li
                  key={child.id}
                  className={cn("relative", deletedId === child.id && "opacity-50")}
                >
                  <span
                    className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-4 h-2 w-2 rounded-full bg-muted-foreground/40 border border-border/60"
                    aria-hidden
                  />
                  <div className="rounded-lg border border-border/40 bg-muted/30 p-3 sm:p-4 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm">{child.title || child.summary || "Child card"}</p>
                      </div>
                      {isEditingThisChild ? (
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground"
                            onClick={onCancelEditingChild}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            variant="default"
                            onClick={onSubmitEditChild}
                            disabled={isSubmitting}
                          >
                            <Check className="h-4 w-4 mr-1" />
                            Done
                          </Button>
                        </div>
                      ) : (
                        <div className="flex gap-1 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => onStartEditingChild(child)}
                          >
                            <PenLine className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => onDeleteChild(child.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                    {isEditingThisChild ? (
                      <ChildCardEditForm
                        form={childEditForm}
                        onChange={onChildEditFormChange}
                        onSubmit={onSubmitEditChild}
                        onDelete={() => onDeleteChild(child.id)}
                        isSubmitting={isSubmitting}
                      />
                    ) : (
                      (child.summary || child.company || child.time_range) && (
                        <div className="mt-2 pt-2 border-t border-border/40 text-xs text-muted-foreground space-y-0.5">
                          {child.summary && <p className="line-clamp-2">{child.summary}</p>}
                          <div className="flex flex-wrap gap-x-3">
                            {child.company && <span>{child.company}</span>}
                            {child.time_range && <span>{child.time_range}</span>}
                          </div>
                        </div>
                      )
                    )}
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
