import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Check } from "lucide-react";
import { MessyTextVoiceInput } from "../voice/messy-text-voice-input";

interface ChildCardEditFormProps {
  form: {
    title: string;
    summary: string;
    tagsStr: string;
    time_range: string;
    location: string;
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
          <Label className="text-xs font-medium">Add Or Fix With Messy Text</Label>
          <p className="text-[11px] text-muted-foreground text-left">
            Paste extra details (e.g. dates, role, location). We&apos;ll parse and fill only empty fields.
          </p>
          <MessyTextVoiceInput
            value={messyText}
            onChange={setMessyText}
            placeholder="e.g. 2021-2022, Python, AWS..."
            rows={2}
          />
        </div>
      )}

      <div className="mt-3 space-y-3">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <Label className="text-xs font-medium">Title</Label>
            {onUpdateFromMessyText && (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={handleUpdateFromMessy}
                disabled={!messyText.trim() || isUpdatingFromMessyText}
              >
                {isUpdatingFromMessyText ? "Updating..." : "Update"}
              </Button>
            )}
          </div>
          <Input
            value={form.title}
            onChange={(e) => onChange({ title: e.target.value })}
            className="bg-background text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Summary</Label>
          <Textarea
            value={form.summary}
            onChange={(e) => onChange({ summary: e.target.value })}
            rows={2}
            className="resize-y bg-background text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Tags (comma-separated)</Label>
          <Input
            value={form.tagsStr}
            onChange={(e) => onChange({ tagsStr: e.target.value })}
            className="bg-background text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Time range</Label>
          <Input
            value={form.time_range}
            onChange={(e) => onChange({ time_range: e.target.value })}
            className="bg-background text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Location</Label>
          <Input
            value={form.location}
            onChange={(e) => onChange({ location: e.target.value })}
            className="bg-background text-sm"
          />
        </div>
      </div>
    </div>
  );
}
