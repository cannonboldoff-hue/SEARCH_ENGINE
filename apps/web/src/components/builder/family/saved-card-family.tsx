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
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 280, damping: 26 }}
      className={cn("relative max-w-full min-w-0", deletedId === parentId && "opacity-50")}
    >
      <div className="border border-border rounded-lg bg-card overflow-hidden hover:border-border/80 transition-colors">
        <div className="p-4 sm:p-5 min-w-0">
          <div className="flex items-start justify-between gap-3 w-full min-w-0">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-base text-foreground truncate">
                {displayCardTitle(parent.title, parent.company_name || "Untitled")}
              </h3>
              {(parent.company_name || parent.location) && (
                <p className="text-sm text-muted-foreground mt-1">
                  {[parent.company_name, parent.location].filter(Boolean).join(" • ")}
                </p>
              )}
              {(parent.start_date != null || parent.end_date != null || parent.is_current) && (
                <p className="text-xs text-muted-foreground mt-1 font-mono">
                  {[parent.start_date, parent.end_date ?? (parent.is_current ? "Ongoing" : null)].filter(Boolean).join(" – ")}
                </p>
              )}
            </div>
            {!isEditingParent && (
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
            <V1CardDetails card={parent as unknown as Record<string, unknown>} summaryFullWidth hideInternalFields compact />
          )}
        </div>
      </div>

      {visibleChildren.length > 0 && (
        <div className="border-t border-border bg-secondary/20 p-4 sm:p-5 space-y-3">
          {visibleChildren.map((child, childIdx) => {
            const isEditingThisChild = editingSavedChildId === child.id;
            const relationType = (child.relation_type ?? "").toString().trim();
            const relationDisplay = relationType ? relationType.replace(/_/g, " ").toUpperCase() : "";

            return (
              <motion.div
                key={child.id}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: childIdx * 0.05, duration: 0.2 }}
                className={cn(
                  "border border-border/40 rounded bg-background/50 p-3 transition-opacity",
                  deletedId === child.id && "opacity-50"
                )}
              >
                {!isEditingThisChild && (
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      {relationDisplay && (
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1 font-medium">
                          {relationDisplay}
                        </p>
                      )}
                      <p className="font-medium text-sm text-foreground">
                        {displayCardTitle(child.title, child.summary || "Detail")}
                      </p>
                      {child.summary && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{child.summary}</p>
                      )}
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
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
                {isEditingThisChild && (
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
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
