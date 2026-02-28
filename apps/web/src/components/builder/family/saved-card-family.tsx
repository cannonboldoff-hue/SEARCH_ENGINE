import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ParentCardEditForm } from "../forms/parent-card-edit-form";
import { ChildCardEditForm } from "../forms/child-card-edit-form";
import {
  CardDetails,
  displayCardTitle,
  getChildDisplayItems,
  getLocationFromCard,
  isPlaceholderChildCard,
} from "../card/card-details";
import { PenLine, Trash2, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ExperienceCard, ExperienceCardChild } from "@/types";
import type { ParentCardForm, ChildCardForm } from "@/hooks/use-card-forms";

interface SavedCardFamilyProps {
  parent: ExperienceCard;
  children: ExperienceCardChild[];
  /** When true, hides edit/delete and only allows expand + child detail pop-out */
  readOnly?: boolean;
  deletedId?: string | null;
  editingSavedCardId?: string | null;
  editingSavedChildId?: string | null;
  editForm?: ParentCardForm;
  childEditForm?: ChildCardForm;
  onEditFormChange?: (updates: Partial<ParentCardForm>) => void;
  onChildEditFormChange?: (updates: Partial<ChildCardForm>) => void;
  onStartEditing?: (card: ExperienceCard) => void;
  onStartEditingChild?: (child: ExperienceCardChild) => void;
  onCancelEditing?: () => void;
  onCancelEditingChild?: () => void;
  onSubmitEdit?: () => void;
  onSubmitEditChild?: () => void;
  onDelete?: (id: string) => void;
  onDeleteChild?: (id: string) => void;
  isSubmitting?: boolean;
  onUpdateParentFromMessyText?: (text: string) => Promise<void>;
  onUpdateChildFromMessyText?: (text: string) => Promise<void>;
  isUpdatingFromMessyText?: boolean;
  translateRawText?: (text: string) => Promise<string>;
}

export function SavedCardFamily({
  parent,
  children,
  readOnly = false,
  deletedId = null,
  editingSavedCardId = null,
  editingSavedChildId = null,
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
  isSubmitting = false,
  onUpdateParentFromMessyText,
  onUpdateChildFromMessyText,
  isUpdatingFromMessyText = false,
  translateRawText,
}: SavedCardFamilyProps) {
  const parentId = String(
    (parent as { id?: string })?.id ?? (parent as Record<string, unknown>)?.card_id ?? ""
  ).trim();
  const isEditingParent = !readOnly && editingSavedCardId === parentId;
  const visibleChildren = children.filter((c) => !isPlaceholderChildCard(c as Record<string, unknown>));
  const hasChildren = visibleChildren.length > 0;
  const [isExpanded, setIsExpanded] = useState(false);
  const [viewingChildId, setViewingChildId] = useState<string | null>(null);

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
      {/* Parent card - flat, open (no inset look) */}
      <div
        className={cn(
          "group rounded-xl border border-border bg-card p-4 transition-colors",
          hasChildren && !isEditingParent && "cursor-pointer hover:bg-accent/30"
        )}
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
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-[16px] text-foreground leading-snug">
              {displayCardTitle(parent.title, parent.company_name || "Untitled")}
            </h3>
            {!isEditingParent &&
              (() => {
                const company =
                  parent.company_name && displayCardTitle(parent.title, parent.company_name || "") !== parent.company_name.trim()
                    ? parent.company_name
                    : null;
                const location = getLocationFromCard(parent);
                const parts = [company, location].filter(Boolean);
                return parts.length > 0 ? (
                  <p className="text-sm text-[rgba(237,237,237,0.6)] leading-[15px] mt-0.5">{parts.join(" · ")}</p>
                ) : null;
              })()}
            <CardDetails
              card={parent as unknown as Record<string, unknown>}
              summaryFullWidth
              hideInternalFields
              hideLocation
            />
          </div>
          {!isEditingParent && (
            <div className="flex items-center gap-2 flex-shrink-0">
              {hasChildren && (
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground tabular-nums">{visibleChildren.length}</span>
                  <motion.div
                    animate={{ rotate: isExpanded ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-muted-foreground"
                  >
                    <ChevronDown className="h-4 w-4" aria-hidden />
                  </motion.div>
                </div>
              )}
              {!readOnly && (
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-muted-foreground hover:text-foreground h-7 w-7 p-0"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onStartEditing?.(parent);
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
                      if (parentId) onDelete?.(parentId);
                    }}
                    disabled={!parentId}
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Children - hierarchy/timeline style (thread line + nodes, not inside card) */}
      <AnimatePresence initial={false}>
        {hasChildren && !isEditingParent && isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="relative pl-7 pt-0" onClick={(e) => e.stopPropagation()}>
              <span
                className="thread-line thread-line-animated top-0 bottom-4"
                aria-hidden
              />
              <ul className="relative space-y-0">
                {visibleChildren.map((child, childIdx) => {
                  const relationType = (child.child_type ?? "").toString().trim();
                  const relationDisplay = relationType ? relationType.replace(/_/g, " ") : "";

                  return (
                    <motion.li
                      key={child.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{
                        delay: childIdx * 0.06,
                        duration: 0.25,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                      className={cn(
                        "relative py-2.5 first:pt-3 group/child",
                        deletedId === child.id && "opacity-50"
                      )}
                    >
                      <span
                        className={cn(
                          "thread-node thread-node-sm thread-node-animated",
                          "top-1/2 -translate-y-1/2",
                          editingSavedChildId === child.id && "thread-node-active"
                        )}
                        style={{ animationDelay: `${childIdx * 60 + 100}ms` }}
                        aria-hidden
                      />
                      <div
                        className="ml-5 rounded-lg border border-border/60 bg-accent/30 px-3 py-2.5 transition-colors hover:bg-accent/50 cursor-pointer"
                        onClick={() => setViewingChildId(child.id)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            {relationDisplay && (
                              <span className="inline-block text-sm text-left align-bottom text-foreground font-medium leading-snug mb-2.5 tracking-normal uppercase">
                                {relationDisplay}
                              </span>
                            )}
                            <p className="flex flex-wrap text-sm font-medium text-foreground/60 leading-snug px-2.5 whitespace-pre-line">
                              {(() => {
                                const items = getChildDisplayItems(child);
                                const childType = (child.child_type ?? "").toString().trim().replace(/_/g, " ");
                                if (items.length === 0) return childType || "Detail";
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
                          {!readOnly && (
                            <div
                              className="flex gap-0.5 flex-shrink-0 opacity-0 group-hover/child:opacity-100 transition-opacity"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-muted-foreground hover:text-foreground h-6 w-6 p-0"
                                onClick={() => onStartEditingChild?.(child)}
                              >
                                <PenLine className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-muted-foreground hover:text-destructive h-6 w-6 p-0"
                                onClick={() => onDeleteChild?.(child.id)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.li>
                  );
                })}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Child detail modal - pops out when child card is clicked */}
      <AnimatePresence>
        {viewingChildId && (() => {
          const child = visibleChildren.find((c) => c.id === viewingChildId);
          if (!child) return null;
          const relationType = (child.child_type ?? "").toString().trim();
          const relationDisplay = relationType ? relationType.replace(/_/g, " ") : "";

          return (
            <motion.div
              key={`view-child-${viewingChildId}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
              onClick={() => setViewingChildId(null)}
            >
              <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" aria-hidden />
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 12 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 12 }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
                className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border bg-card shadow-xl"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="py-[10px] px-[15px] sm:p-6">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="min-w-0 flex-1">
                      {relationDisplay && (
                        <span className="inline-block text-[16px] uppercase tracking-wider text-primary/60 font-medium mb-0.5">
                          {relationDisplay}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      {!readOnly && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setViewingChildId(null);
                            onStartEditingChild?.(child);
                          }}
                          className="gap-1.5"
                        >
                          <PenLine className="h-3.5 w-3.5" />
                          Edit
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setViewingChildId(null)}
                      >
                        Close
                      </Button>
                    </div>
                  </div>
                  <div className="border-t border-border/60">
                    <CardDetails
                      card={child as unknown as Record<string, unknown>}
                      compact={false}
                      summaryFullWidth
                      hideInternalFields
                      hideSummary
                    />
                  </div>
                </div>
              </motion.div>
            </motion.div>
          );
        })()}
      </AnimatePresence>

      {/* Edit modal - pops out when pencil is clicked (only in editable mode) */}
      <AnimatePresence>
        {!readOnly &&
          editForm &&
          childEditForm &&
          onEditFormChange &&
          onChildEditFormChange &&
          onCancelEditing &&
          onCancelEditingChild &&
          onSubmitEdit &&
          onSubmitEditChild &&
          (isEditingParent || (editingSavedChildId && visibleChildren.some((c) => c.id === editingSavedChildId))) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                isEditingParent ? onCancelEditing?.() : onCancelEditingChild?.();
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
