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
              <span className="font-semibold text-sm truncate text-foreground">
                {parent.title || parent.company_name || "Untitled"}
              </span>
              {children.length > 0 && (
                <span className="text-xs text-muted-foreground flex-shrink-0 tabular-nums">
                  {children.length} thread{children.length !== 1 ? "s" : ""}
                </span>
              )}
            </span>
            {isEditingParent ? (
              <div className="flex items-center gap-1 flex-shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground h-7 px-2"
                  onClick={onCancelEditing}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="default"
                  className="h-7"
                  onClick={onSubmitEdit}
                  disabled={isSubmitting}
                >
                  <Check className="h-3.5 w-3.5 mr-1" />
                  Done
                </Button>
              </div>
            ) : (
              <div className="flex gap-0.5 flex-shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                  onClick={() => onStartEditing(parent)}
                >
                  <PenLine className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-destructive h-7 w-7 p-0"
                  onClick={() => onDelete(parent.id)}
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

      {/* ── Thread children ── */}
      {children.length > 0 && (
        <div className="relative pl-7 pt-0 mt-0">
          {/* Vertical thread line */}
          <span
            className="thread-line top-0 bottom-3"
            aria-hidden
          />

          <ul className="relative space-y-0">
            {children.map((child, childIdx) => {
              const isEditingThisChild = editingSavedChildId === child.id;

              return (
                <motion.li
                  key={child.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: childIdx * 0.06, duration: 0.2 }}
                  className={cn(
                    "relative py-2 first:pt-3",
                    deletedId === child.id && "opacity-50"
                  )}
                >
                  {/* Thread node */}
                  <span
                    className={cn(
                      "thread-node thread-node-sm",
                      "top-1/2 -translate-y-1/2",
                      isEditingThisChild && "thread-node-active"
                    )}
                    aria-hidden
                  />

                  {/* Child block */}
                  <div className="ml-5 rounded-lg border border-border/40 bg-accent/30 px-3 py-2.5 transition-colors hover:bg-accent/50">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-sm text-foreground">
                          {child.title || child.summary || "Detail"}
                        </p>
                      </div>
                      {isEditingThisChild ? (
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground h-7 px-2"
                            onClick={onCancelEditingChild}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            variant="default"
                            className="h-7"
                            onClick={onSubmitEditChild}
                            disabled={isSubmitting}
                          >
                            <Check className="h-3.5 w-3.5 mr-1" />
                            Done
                          </Button>
                        </div>
                      ) : (
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
                            onClick={() => onDeleteChild(child.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
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
                        <div className="mt-1.5 pt-1.5 border-t border-border/30 text-xs text-muted-foreground space-y-0.5">
                          {child.summary && <p className="line-clamp-2">{child.summary}</p>}
                          <div className="flex flex-wrap gap-x-3">
                            {child.company && <span>{child.company}</span>}
                            {child.time_range && <span>{child.time_range}</span>}
                          </div>
                        </div>
                      )
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
