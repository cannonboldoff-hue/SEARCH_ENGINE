import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Check } from "lucide-react";

interface ParentCardEditFormProps {
  form: {
    title: string;
    summary: string;
    normalized_role: string;
    domain: string;
    sub_domain: string;
    company_name: string;
    company_type: string;
    location: string;
    employment_type: string;
    start_date: string;
    end_date: string;
    is_current: boolean;
    intent_primary: string;
    intent_secondary_str: string;
    seniority_level: string;
    confidence_score: string;
    experience_card_visibility: boolean;
  };
  onChange: (updates: Partial<ParentCardEditFormProps["form"]>) => void;
  onSubmit: () => void;
  onDelete?: () => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
  isDeleting?: boolean;
  checkboxIdPrefix?: string;
  /** When false, the Delete button is hidden (e.g. when editing – use dustbin on card instead). */
  showDeleteButton?: boolean;
  /** Optional: paste messy text and click Update to fill missing fields from parsed result. */
  onUpdateFromMessyText?: (text: string) => Promise<void>;
  isUpdatingFromMessyText?: boolean;
}

export function ParentCardEditForm({
  form,
  onChange,
  onSubmit,
  onDelete,
  onCancel,
  isSubmitting = false,
  isDeleting = false,
  checkboxIdPrefix = "edit",
  showDeleteButton = false,
  onUpdateFromMessyText,
  isUpdatingFromMessyText = false,
}: ParentCardEditFormProps) {
  const [messyText, setMessyText] = useState("");

  const handleUpdateFromMessy = async () => {
    if (!messyText.trim() || !onUpdateFromMessyText) return;
    await onUpdateFromMessyText(messyText.trim());
  };

  return (
    <div className="mt-3 rounded-xl border border-border/60 bg-background/80 p-3 sm:p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2 pb-3 border-b border-border/50">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Editing Experience</p>
        <div className="flex items-center gap-1 flex-shrink-0">
          {onCancel && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-muted-foreground h-8 px-2"
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
              className="text-destructive hover:text-destructive hover:bg-destructive/10 h-8 px-2"
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
            <Check className="h-4 w-4 mr-1" />
            Done
          </Button>
        </div>
      </div>

      {onUpdateFromMessyText && (
        <div className="mt-3 rounded-lg border border-border/50 bg-muted/30 p-3 space-y-2">
          <Label className="text-xs font-medium">Add Or Fix With Messy Text</Label>
          <p className="text-[11px] text-muted-foreground">
            Paste extra details (e.g. dates, role, location). We&apos;ll parse and fill only empty fields.
          </p>
          <Textarea
            value={messyText}
            onChange={(e) => setMessyText(e.target.value)}
            placeholder="e.g. Worked from Jan 2020 to 2022, full-time, Bangalore..."
            rows={2}
            className="text-sm resize-y bg-background"
          />
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
      )}

      <div className="mt-3 space-y-3">
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Title</Label>
          <Input
            value={form.title}
            onChange={(e) => onChange({ title: e.target.value })}
            placeholder="Card title"
            className="text-sm bg-background"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Summary</Label>
          <Textarea
            value={form.summary}
            onChange={(e) => onChange({ summary: e.target.value })}
            placeholder="A short summary"
            rows={3}
            className="text-sm resize-y bg-background"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Domain</Label>
            <Input
              value={form.domain}
              onChange={(e) => onChange({ domain: e.target.value })}
              placeholder="e.g. Payments"
              className="text-sm bg-background"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Sub-domain</Label>
            <Input
              value={form.sub_domain}
              onChange={(e) => onChange({ sub_domain: e.target.value })}
              placeholder="e.g. Risk"
              className="text-sm bg-background"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Start date</Label>
            <Input
              type="date"
              value={form.start_date}
              onChange={(e) => onChange({ start_date: e.target.value })}
              className="text-sm bg-background"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">End date</Label>
            <Input
              type="date"
              value={form.end_date}
              onChange={(e) => onChange({ end_date: e.target.value })}
              className="text-sm bg-background"
            />
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-md border border-border/50 bg-muted/20 px-3 py-2">
          <input
            type="checkbox"
            id={`${checkboxIdPrefix}-is-current`}
            checked={form.is_current}
            onChange={(e) => onChange({ is_current: e.target.checked })}
            className="rounded border-border"
          />
          <Label htmlFor={`${checkboxIdPrefix}-is-current`} className="text-xs cursor-pointer">Current / ongoing</Label>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Company</Label>
            <Input
              value={form.company_name}
              onChange={(e) => onChange({ company_name: e.target.value })}
              placeholder="Company"
              className="text-sm bg-background"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Location</Label>
            <Input
              value={form.location}
              onChange={(e) => onChange({ location: e.target.value })}
              placeholder="City / location"
              className="text-sm bg-background"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Company type</Label>
            <Input
              value={form.company_type}
              onChange={(e) => onChange({ company_type: e.target.value })}
              placeholder="e.g. Startup"
              className="text-sm bg-background"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Employment type</Label>
            <Input
              value={form.employment_type}
              onChange={(e) => onChange({ employment_type: e.target.value })}
              placeholder="e.g. Full-time"
              className="text-sm bg-background"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Role (normalized)</Label>
          <Input
            value={form.normalized_role}
            onChange={(e) => onChange({ normalized_role: e.target.value })}
            placeholder="e.g. Backend Engineer"
            className="text-sm bg-background"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Seniority</Label>
            <Input
              value={form.seniority_level}
              onChange={(e) => onChange({ seniority_level: e.target.value })}
              placeholder="e.g. Senior"
              className="text-sm bg-background"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-medium">Confidence score</Label>
            <Input
              type="number"
              step="0.01"
              value={form.confidence_score}
              onChange={(e) => onChange({ confidence_score: e.target.value })}
              placeholder="e.g. 0.75"
              className="text-sm bg-background"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Intent (primary)</Label>
          <Input
            value={form.intent_primary}
            onChange={(e) => onChange({ intent_primary: e.target.value })}
            placeholder="e.g. work"
            className="text-sm bg-background"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs font-medium">Intent (secondary, comma-separated)</Label>
          <Input
            value={form.intent_secondary_str}
            onChange={(e) => onChange({ intent_secondary_str: e.target.value })}
            placeholder="e.g. learning, project"
            className="text-sm bg-background"
          />
        </div>
        <div className="flex items-center gap-2 rounded-md border border-border/50 bg-muted/20 px-3 py-2">
          <input
            type="checkbox"
            id={`${checkboxIdPrefix}-visible`}
            checked={form.experience_card_visibility}
            onChange={(e) => onChange({ experience_card_visibility: e.target.checked })}
            className="rounded border-border"
          />
          <Label htmlFor={`${checkboxIdPrefix}-visible`} className="text-xs cursor-pointer">Visible</Label>
        </div>
      </div>
    </div>
  );
}
