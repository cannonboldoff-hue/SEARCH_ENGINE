import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Check } from "lucide-react";

interface ChildCardEditFormProps {
  form: {
    title: string;
    summary: string;
    tagsStr: string;
    time_range: string;
    company: string;
    location: string;
  };
  onChange: (updates: Partial<ChildCardEditFormProps["form"]>) => void;
  onSubmit: () => void;
  onDelete?: () => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
  isDeleting?: boolean;
  /** When false, the Delete button is hidden (e.g. when editing – use dustbin on card instead). */
  showDeleteButton?: boolean;
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
}: ChildCardEditFormProps) {
  return (
    <>
      <div className="flex items-center gap-1 flex-shrink-0">
        {onCancel && (
          <Button
            size="sm"
            variant="ghost"
            className="text-muted-foreground h-7 px-2"
            onClick={onCancel}
          >
            Cancel
          </Button>
        )}
        {showDeleteButton && onDelete && (
          <Button
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={onDelete}
            disabled={isDeleting}
          >
            Delete
          </Button>
        )}
        <Button
          size="sm"
          variant="default"
          onClick={onSubmit}
          disabled={isSubmitting}
        >
          <Check className="h-4 w-4 mr-1" />
          Done
        </Button>
      </div>

      <div className="mt-3 space-y-3 pt-3 border-t border-border/40">
        <div className="space-y-1.5">
          <Label className="text-xs">Title</Label>
          <Input
            value={form.title}
            onChange={(e) => onChange({ title: e.target.value })}
            className="text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Summary</Label>
          <Textarea
            value={form.summary}
            onChange={(e) => onChange({ summary: e.target.value })}
            rows={2}
            className="text-sm resize-y"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Tags (comma-separated)</Label>
          <Input
            value={form.tagsStr}
            onChange={(e) => onChange({ tagsStr: e.target.value })}
            className="text-sm"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Time range</Label>
            <Input
              value={form.time_range}
              onChange={(e) => onChange({ time_range: e.target.value })}
              className="text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Company</Label>
            <Input
              value={form.company}
              onChange={(e) => onChange({ company: e.target.value })}
              className="text-sm"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Location</Label>
          <Input
            value={form.location}
            onChange={(e) => onChange({ location: e.target.value })}
            className="text-sm"
          />
        </div>
      </div>
    </>
  );
}
