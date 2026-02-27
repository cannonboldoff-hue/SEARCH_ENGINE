import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ParentCardEditForm } from "../forms/parent-card-edit-form";
import { ChildCardEditForm } from "../forms/child-card-edit-form";
import { V1CardDetails, displayCardTitle, isPlaceholderChildCard } from "../card/v1-card-details";
import { PenLine, Trash2, ChevronRight, ChevronDown } from "lucide-react";
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
  const hasChildren = visibleChildren.length > 0;
  const [isExpanded, setIsExpanded] = useState(false);

  const handleParentClick = () => {
    if (!hasChildren || isEditingParent) return;
    if (editingSavedChildId && visibleChildren.some((c) => c.id === editingSavedChildId)) return;
    setIsExpanded((prev) => !prev);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 28 }}
      className={cn("relative", deletedId === parentId && "opacity-50")}
    >
      {/* Parent card */}
      <div className={cn(
        "group rounded-2xl border border-border/40 bg-card overflow-hidden",
        "transition-all duration-200",
        "hover:border-border/70 hover:shadow-md",
        hasChildren && !isEditingParent && "cursor-pointer",
      )}>
        <div
          className="p-4 sm:p-5"
          onClick={handleParentClick}
          onKeyDown={(e) => {
            if (hasChildren && !isEditingParent && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              setIsExpanded((prev) => !prev);
            }
          }}
          role={hasChildren && !isEditingParent ? "button" : undefined}
          tabIndex={hasChildren && !isEditingParent ? 0 : undefined}
          aria-expanded={hasChildren && !isEditingParent ? isExpanded : undefined}
        >
          {/* Header row */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 flex items-start gap-2">
              {hasChildren && !isEditingParent && (
                <ChevronDown
                  className={cn("h-4 w-4 flex-shrink-0 text-muted-foreground mt-0.5 transition-transform duration-200", !isExpanded && "-rotate-90")}
                  aria-hidden
                />
              )}
              <div className="min-w-0 flex-1">
              <h3 className="font-semibold text-[15px] text-foreground leading-snug">
                {displayCardTitle(parent.title, parent.company_name || "Untitled")}
              </h3>
              {!isEditingParent && (parent.start_date != null || parent.end_date != null || parent.is_current) && (
                <p className="text-xs text-muted-foreground/70 mt-0.5 tabular-nums">
                  {[parent.start_date, parent.end_date ?? (parent.is_current ? "Ongoing" : null)].filter(Boolean).join(" – ")}
                </p>
              )}
              </div>
            </div>
            {!isEditingParent && (
              <div className="flex gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
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
                  className="text-muted-foreground hover:text-destructive h-7 w-7 p-0"
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

          {/* Content - always read-only; edit opens in modal */}
          <V1CardDetails card={parent as unknown as Record<string, unknown>} summaryFullWidth hideInternalFields />
        </div>

        {/* Children section - clean inline list (dropdown) */}
        <AnimatePresence initial={false}>
          {hasChildren && !isEditingParent && isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <div className="border-t border-border/30 bg-muted/20 px-4 sm:px-5 py-3" onClick={(e) => e.stopPropagation()}>
                <div className="space-y-2">
              {visibleChildren.map((child, childIdx) => {
                const isEditingThisChild = editingSavedChildId === child.id;
                const relationType = (child.relation_type ?? "").toString().trim();
                const relationDisplay = relationType ? relationType.replace(/_/g, " ") : "";

                return (
                  <motion.div
                    key={child.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: childIdx * 0.04, duration: 0.15 }}
                    className={cn(
                      "group/child",
                      deletedId === child.id && "opacity-50"
                    )}
                  >
                    <div className="flex items-start gap-2.5 rounded-lg px-2.5 py-2 -mx-1 transition-colors hover:bg-muted/40">
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 mt-0.5 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              {relationDisplay && (
                                <span className="inline-block text-[10px] uppercase tracking-wider text-primary/60 font-medium mb-0.5">
                                  {relationDisplay}
                                </span>
                              )}
                              <p className="text-sm font-medium text-foreground leading-snug">
                                {displayCardTitle(child.title, child.summary || "Detail")}
                              </p>
                              {child.summary && (
                                <p className="text-xs text-muted-foreground/70 mt-0.5 line-clamp-1">
                                  {child.summary}
                                </p>
                              )}
                              {child.time_range && (
                                <p className="text-[11px] text-muted-foreground/50 mt-0.5">{child.time_range}</p>
                              )}
                              {Array.isArray(child.tags) && child.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1.5">
                                  {child.tags.map((tag, i) => (
                                    <span
                                      key={`${tag}-${i}`}
                                      className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary/80"
                                    >
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                            <div className="flex gap-0.5 flex-shrink-0 opacity-0 group-hover/child:opacity-100 transition-opacity">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-muted-foreground hover:text-foreground h-6 w-6 p-0"
                                onClick={() => onStartEditingChild(child)}
                              >
                                <PenLine className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-muted-foreground hover:text-destructive h-6 w-6 p-0"
                                onClick={() => onDeleteChild(child.id)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                  </motion.div>
                );
              })}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Edit modal - pops out when pencil is clicked */}
      <AnimatePresence>
        {(isEditingParent || (editingSavedChildId && visibleChildren.some((c) => c.id === editingSavedChildId))) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                isEditingParent ? onCancelEditing() : onCancelEditingChild();
              }
            }}
          >
            <div
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
              aria-hidden
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border bg-card shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
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
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
