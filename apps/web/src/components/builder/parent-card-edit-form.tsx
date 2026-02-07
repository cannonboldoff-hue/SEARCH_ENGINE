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
    visibility: boolean;
  };
  onChange: (updates: Partial<ParentCardEditFormProps["form"]>) => void;
  onSubmit: () => void;
  onDelete: () => void;
  isSubmitting?: boolean;
  isDeleting?: boolean;
  checkboxIdPrefix?: string;
}

export function ParentCardEditForm({
  form,
  onChange,
  onSubmit,
  onDelete,
  isSubmitting = false,
  isDeleting = false,
  checkboxIdPrefix = "edit",
}: ParentCardEditFormProps) {
  return (
    <>
      <div className="flex items-center gap-1 flex-shrink-0">
        <Button
          size="sm"
          variant="ghost"
          className="text-destructive hover:text-destructive hover:bg-destructive/10"
          onClick={onDelete}
          disabled={isDeleting}
        >
          Delete
        </Button>
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

      <div className="mt-3 space-y-3 pt-3 border-t border-border/50">
        <div className="space-y-1.5">
          <Label className="text-xs">Title</Label>
          <Input
            value={form.title}
            onChange={(e) => onChange({ title: e.target.value })}
            placeholder="Card title"
            className="text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Summary</Label>
          <Textarea
            value={form.summary}
            onChange={(e) => onChange({ summary: e.target.value })}
            placeholder="A short summary"
            rows={3}
            className="text-sm resize-y"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Domain</Label>
            <Input
              value={form.domain}
              onChange={(e) => onChange({ domain: e.target.value })}
              placeholder="e.g. Payments"
              className="text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Sub-domain</Label>
            <Input
              value={form.sub_domain}
              onChange={(e) => onChange({ sub_domain: e.target.value })}
              placeholder="e.g. Risk"
              className="text-sm"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Start date</Label>
            <Input
              type="date"
              value={form.start_date}
              onChange={(e) => onChange({ start_date: e.target.value })}
              className="text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">End date</Label>
            <Input
              type="date"
              value={form.end_date}
              onChange={(e) => onChange({ end_date: e.target.value })}
              className="text-sm"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
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
            <Label className="text-xs">Company</Label>
            <Input
              value={form.company_name}
              onChange={(e) => onChange({ company_name: e.target.value })}
              placeholder="Company"
              className="text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Location</Label>
            <Input
              value={form.location}
              onChange={(e) => onChange({ location: e.target.value })}
              placeholder="City / location"
              className="text-sm"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Company type</Label>
            <Input
              value={form.company_type}
              onChange={(e) => onChange({ company_type: e.target.value })}
              placeholder="e.g. Startup"
              className="text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Employment type</Label>
            <Input
              value={form.employment_type}
              onChange={(e) => onChange({ employment_type: e.target.value })}
              placeholder="e.g. Full-time"
              className="text-sm"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Role (normalized)</Label>
          <Input
            value={form.normalized_role}
            onChange={(e) => onChange({ normalized_role: e.target.value })}
            placeholder="e.g. Backend Engineer"
            className="text-sm"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Seniority</Label>
            <Input
              value={form.seniority_level}
              onChange={(e) => onChange({ seniority_level: e.target.value })}
              placeholder="e.g. Senior"
              className="text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Confidence score</Label>
            <Input
              type="number"
              step="0.01"
              value={form.confidence_score}
              onChange={(e) => onChange({ confidence_score: e.target.value })}
              placeholder="e.g. 0.75"
              className="text-sm"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Intent (primary)</Label>
          <Input
            value={form.intent_primary}
            onChange={(e) => onChange({ intent_primary: e.target.value })}
            placeholder="e.g. work"
            className="text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Intent (secondary, comma-separated)</Label>
          <Input
            value={form.intent_secondary_str}
            onChange={(e) => onChange({ intent_secondary_str: e.target.value })}
            placeholder="e.g. learning, project"
            className="text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id={`${checkboxIdPrefix}-visible`}
            checked={form.visibility}
            onChange={(e) => onChange({ visibility: e.target.checked })}
            className="rounded border-border"
          />
          <Label htmlFor={`${checkboxIdPrefix}-visible`} className="text-xs cursor-pointer">Visible</Label>
        </div>
      </div>
    </>
  );
}
