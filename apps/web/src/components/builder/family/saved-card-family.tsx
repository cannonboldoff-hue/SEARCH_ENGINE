import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { TiltCard } from "@/components/tilt-card";
import { ParentCardEditForm } from "../forms/parent-card-edit-form";
import { ChildCardEditForm } from "../forms/child-card-edit-form";
import { V1CardDetails, displayCardTitle, isPlaceholderChildCard } from "../card/v1-card-details";
import { PenLine, Trash2 } from "lucide-react";
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
  onUpdateParentFromMessyText?: (text: string) => Promise<void>;
  onUpdateChildFromMessyText?: (text: string) => Promise<void>;
  isUpdatingFromMessyText?: boolean;
  translateRawText?: (text: string) => Promise<string>;
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
  onUpdateParentFromMessyText,
  onUpdateChildFromMessyText,
  isUpdatingFromMessyText = false,
  translateRawText,
}: SavedCardFamilyProps) {
  const parentId = String(
    (parent as { id?: string })?.id ?? (parent as Record<string, unknown>)?.card_id ?? ""
  ).trim();
  const isEditingParent = editingSavedCardId === parentId;
  const visibleChildren = children.filter((c) => !isPlaceholderChildCard(c as Record<string, unknown>));

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, rotateX: -12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, rotateX: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 280, damping: 26 }}
      style={{ transformStyle: "preserve-3d", perspective: 800 }}
      className={cn("relative max-w-full min-w-0", deletedId === parentId && "opacity-50")}
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
          <div className="flex items-start justify-between gap-2 w-full min-w-0">
            <span className="flex items-center gap-2 min-w-0 flex-1 truncate">
              <span className="font-semibold text-sm truncate text-foreground">
                {displayCardTitle(parent.title, parent.company_name || "Untitled")}
              </span>
            </span>
            {isEditingParent ? (
              <span className="flex-shrink-0" />
            ) : (
              <div className="relative z-[100] flex gap-0.5 flex-shrink-0 isolate">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-foreground h-7 w-7 p-0 touch-manipulation"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onStartEditing(parent);
                  }}
                >
                  <PenLine className="h-3.5 w-3.5" aria-hidden />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-destructive h-7 w-7 p-0 touch-manipulation"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (parentId) onDelete(parentId);
                  }}
                  disabled={!parentId}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </Button>
              </div>
            )}
          </div>
          {!isEditingParent && (parent.start_date != null || parent.end_date != null || parent.is_current) && (
            <p className="text-xs text-muted-foreground mt-1 tabular-nums">
              {[parent.start_date, parent.end_date ?? (parent.is_current ? "Ongoing" : null)].filter(Boolean).join(" – ")}
            </p>
          )}
          {isEditingParent ? (
            <ParentCardEditForm
              form={editForm}
              onChange={onEditFormChange}
              onSubmit={onSubmitEdit}
              onCancel={onCancelEditing}
              isSubmitting={isSubmitting}
              checkboxIdPrefix={`edit-saved-${parentId}`}
              showDeleteButton={false}
              onUpdateFromMessyText={onUpdateParentFromMessyText}
              isUpdatingFromMessyText={isUpdatingFromMessyText}
              clarifyCardId={parentId}
              translateRawText={translateRawText}
            />
          ) : (
            <V1CardDetails card={parent as unknown as Record<string, unknown>} summaryFullWidth hideInternalFields />
          )}
        </div>
      </TiltCard>

      {visibleChildren.length > 0 && (
        <div className="relative pl-7 pt-0 mt-0">
          <span
            className="thread-line top-0 bottom-3"
            aria-hidden
          />
          <ul className="relative space-y-0">
            {visibleChildren.map((child, childIdx) => {
              const isEditingThisChild = editingSavedChildId === child.id;
              const relationType = (child.relation_type ?? "").toString().trim();
              const relationDisplay = relationType ? relationType.replace(/_/g, " ").toUpperCase() : "";

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
                  <span
                    className={cn(
                      "thread-node thread-node-sm",
                      "top-1/2 -translate-y-1/2",
                      isEditingThisChild && "thread-node-active"
                    )}
                    aria-hidden
                  />
                  <div className="ml-5 rounded-lg border border-border/40 bg-accent/30 px-3 py-2.5 transition-colors hover:bg-accent/50">
                    {!isEditingThisChild && (
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          {relationDisplay && (
                            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">
                              {relationDisplay}
                            </p>
                          )}
                          <p className="font-medium text-sm text-foreground">
                            {displayCardTitle(child.title, child.summary || "Detail")}
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
                            onClick={() => onDeleteChild(child.id)}
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
                        onCancel={onCancelEditingChild}
                        isSubmitting={isSubmitting}
                        showDeleteButton={false}
                        onUpdateFromMessyText={onUpdateChildFromMessyText}
                        isUpdatingFromMessyText={isUpdatingFromMessyText}
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
