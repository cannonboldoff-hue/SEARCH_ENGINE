import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Check } from "lucide-react";
import { MessyTextVoiceInput, VoiceButton, useVoiceInput } from "@/components/builder/messy-text-voice-input";

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
  /** When false, the Delete button is hidden (e.g. when editing - use dustbin on card instead). */
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
  const voiceInput = useVoiceInput((text) => {
    setMessyText(text);
  });

  const handleUpdateFromMessy = async () => {
    if (!messyText.trim() || !onUpdateFromMessyText) return;
    await onUpdateFromMessyText(messyText.trim());
  };

  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-zinc-950 shadow-sm">
      
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <p className="text-[10px] tracking-widest uppercase text-zinc-400">
          Editing Experience
        </p>
  
        <div className="flex items-center gap-2">
          {onCancel && (
            <Button size="sm" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
  
          {showDeleteButton && onDelete && (
            <Button
              size="sm"
              variant="ghost"
              className="text-red-400 hover:bg-red-500/10"
              onClick={onDelete}
            >
              Delete
            </Button>
          )}
  
          <Button size="sm" onClick={onSubmit} disabled={isSubmitting}>
            <Check className="h-4 w-4 mr-1" />
            Done
          </Button>
        </div>
      </div>
  
      <div className="p-4 space-y-6">
  
        {/* Messy Text */}
        {onUpdateFromMessyText && (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Label className="text-[11px] text-zinc-400 uppercase tracking-wide">
                Update the missing fields.
              </Label>
              <VoiceButton
                isRecording={voiceInput.isRecording}
                isConnectingRecorder={voiceInput.isConnectingRecorder}
                onToggle={voiceInput.toggleRecording}
              />
            </div>
  
            <MessyTextVoiceInput
              value={messyText}
              onChange={setMessyText}
              placeholder="Paste work history…"
              rows={2}
              showButton={false}
            />
          </div>
        )}
  
        {/* BASIC - with Update button */}
        <div>
          <div className="flex items-center justify-between gap-3 mb-3">
            <p className="text-xs uppercase tracking-wide text-zinc-500">Basic</p>
            {onUpdateFromMessyText && (
              <Button
                size="sm"
                variant="secondary"
                onClick={handleUpdateFromMessy}
                disabled={!messyText.trim()}
              >
                Update
              </Button>
            )}
          </div>

          <div className="space-y-3">
            <Input
              value={form.title}
              onChange={(e) => onChange({ title: e.target.value })}
              placeholder="Title"
            />
  
            <Textarea
              value={form.summary}
              onChange={(e) => onChange({ summary: e.target.value })}
              placeholder="Summary"
            />
          </div>
        </div>
  
        {/* COMPANY */}
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Company</p>
  
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              value={form.company_name}
              onChange={(e) => onChange({ company_name: e.target.value })}
              placeholder="Company"
            />
            <Input
              value={form.location}
              onChange={(e) => onChange({ location: e.target.value })}
              placeholder="Location"
            />
            <Input
              value={form.company_type}
              onChange={(e) => onChange({ company_type: e.target.value })}
              placeholder="Type"
            />
            <Input
              value={form.employment_type}
              onChange={(e) => onChange({ employment_type: e.target.value })}
              placeholder="Employment"
            />
          </div>
  
          <Input
            value={form.normalized_role}
            onChange={(e) => onChange({ normalized_role: e.target.value })}
            placeholder="Role"
          />
        </div>
  
        {/* DOMAIN */}
        <div className="grid sm:grid-cols-2 gap-3">
          <Input
            value={form.domain}
            onChange={(e) => onChange({ domain: e.target.value })}
            placeholder="Domain"
          />
          <Input
            value={form.sub_domain}
            onChange={(e) => onChange({ sub_domain: e.target.value })}
            placeholder="Sub-domain"
          />
        </div>
  
        {/* DATES */}
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Dates</p>
  
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              type="date"
              value={form.start_date}
              onChange={(e) => onChange({ start_date: e.target.value })}
            />
            <Input
              type="date"
              value={form.end_date}
              onChange={(e) => onChange({ end_date: e.target.value })}
            />
          </div>
  
          <label className="flex items-center justify-between text-sm text-zinc-300">
            <span>Current role</span>
            <input
              type="checkbox"
              checked={form.is_current}
              onChange={(e) => onChange({ is_current: e.target.checked })}
            />
          </label>
        </div>
  
        {/* META */}
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wide text-zinc-500">Meta</p>
  
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              value={form.seniority_level}
              onChange={(e) => onChange({ seniority_level: e.target.value })}
              placeholder="Seniority"
            />
            <Input
              type="number"
              step="0.01"
              value={form.confidence_score}
              onChange={(e) => onChange({ confidence_score: e.target.value })}
              placeholder="Confidence"
            />
          </div>
  
          <Input
            value={form.intent_primary}
            onChange={(e) => onChange({ intent_primary: e.target.value })}
            placeholder="Primary intent"
          />
  
          <Input
            value={form.intent_secondary_str}
            onChange={(e) => onChange({ intent_secondary_str: e.target.value })}
            placeholder="Secondary intent"
          />
        </div>
  
        {/* VISIBILITY */}
        <label className="flex items-center justify-between text-sm text-zinc-300">
          <span>Visible</span>
          <input
            type="checkbox"
            checked={form.experience_card_visibility}
            onChange={(e) =>
              onChange({ experience_card_visibility: e.target.checked })
            }
          />
        </label>
  
      </div>
    </div>
  );    
}

