import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Check, Plus, Trash2 } from "lucide-react";
import type { ChildValueItem } from "@/types";

interface ChildCardEditFormProps {
  form: {
    title: string;
    summary: string;
    items: ChildValueItem[];
  };
  onChange: (updates: Partial<ChildCardEditFormProps["form"]>) => void;
  onSubmit: () => void;
  onDelete?: () => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
  isDeleting?: boolean;
  /** When false, the Delete button is hidden (e.g. when editing - use dustbin on card instead). */
  showDeleteButton?: boolean;
  /** Optional: paste messy text and click Update to fill missing fields from parsed result. */
  onUpdateFromMessyText?: (text: string) => Promise<void>;
  isUpdatingFromMessyText?: boolean;
}

export function ChildCardEditForm({
  form,
  onChange,
  onSubmit,
  onDelete,
  onCancel,
  isSubmitting = false,
  isDeleting = false,
  showDeleteButton = false,
  onUpdateFromMessyText,
  isUpdatingFromMessyText = false,
}: ChildCardEditFormProps) {
  const [messyText, setMessyText] = useState("");

  const handleUpdateFromMessy = async () => {
    if (!messyText.trim() || !onUpdateFromMessyText) return;
    await onUpdateFromMessyText(messyText.trim());
  };

  return (
    <div className="mt-3 rounded-xl border border-border/60 bg-background/80 p-3 shadow-sm sm:p-4">
      <div className="flex items-center justify-between gap-2 border-b border-border/50 pb-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Editing Detail</p>
        <div className="flex items-center gap-1 flex-shrink-0">
          {onCancel && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2 text-muted-foreground"
              onClick={onCancel}
            >
              Cancel
            </Button>
          )}
          {showDeleteButton && onDelete && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={onDelete}
              disabled={isDeleting}
            >
              Delete
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="default"
            className="h-8 px-3"
            onClick={onSubmit}
            disabled={isSubmitting}
          >
            <Check className="mr-1 h-4 w-4" />
            Done
          </Button>
        </div>
      </div>

      {onUpdateFromMessyText && (
        <div className="mt-3 space-y-2 rounded-lg border border-border/50 bg-muted/30 p-3">
          <div className="flex items-center justify-between gap-2">
            <Label className="text-xs font-medium">Add Or Fix With Messy Text</Label>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={handleUpdateFromMessy}
              disabled={!messyText.trim() || isUpdatingFromMessyText}
            >
              {isUpdatingFromMessyText ? "Updating..." : "Update"}
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground text-left">
            Paste extra details (e.g. title, summary, items). We&apos;ll parse and fill only empty fields.
          </p>
          <Textarea
            value={messyText}
            onChange={(e) => setMessyText(e.target.value)}
            placeholder="e.g. 2021-2022, Python, AWS..."
            rows={2}
            className="text-sm resize-y bg-background"
          />
        </div>
      )}

      <div className="mt-3 space-y-3">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-medium">Items (subtitle, sub_summary)</Label>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={() => onChange({ items: [...form.items, { subtitle: "", sub_summary: null }] })}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add
            </Button>
          </div>
          {form.items.map((item, i) => (
            <div key={i} className="flex gap-2 items-start rounded-lg border border-border/50 p-2 bg-muted/20">
              <div className="flex-1 min-w-0 space-y-1.5">
                <Input
                  value={item.subtitle}
                  onChange={(e) => {
                    const next = [...form.items];
                    next[i] = { ...item, subtitle: e.target.value };
                    onChange({ items: next });
                  }}
                  placeholder="Title"
                  className="bg-background text-sm"
                />
                <Input
                  value={item.sub_summary ?? ""}
                  onChange={(e) => {
                    const next = [...form.items];
                    next[i] = { ...item, sub_summary: e.target.value.trim() || null };
                    onChange({ items: next });
                  }}
                  placeholder="Description"
                  className="bg-background text-sm"
                />
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive shrink-0"
                onClick={() => {
                  const next = form.items.filter((_, j) => j !== i);
                  onChange({ items: next.length > 0 ? next : [{ subtitle: "", sub_summary: null }] });
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
