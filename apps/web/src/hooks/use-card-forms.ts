import { useState, useCallback } from "react";
import type { ExperienceCard, ExperienceCardChild, ExperienceCardV1 } from "@/types";

export interface ParentCardForm {
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
}

export interface ChildCardForm {
  title: string;
  summary: string;
  tagsStr: string;
  time_range: string;
  company: string;
  location: string;
}

const initialParentForm: ParentCardForm = {
  title: "",
  summary: "",
  normalized_role: "",
  domain: "",
  sub_domain: "",
  company_name: "",
  company_type: "",
  location: "",
  employment_type: "",
  start_date: "",
  end_date: "",
  is_current: false,
  intent_primary: "",
  intent_secondary_str: "",
  seniority_level: "",
  confidence_score: "",
  experience_card_visibility: true,
};

const initialChildForm: ChildCardForm = {
  title: "",
  summary: "",
  tagsStr: "",
  time_range: "",
  company: "",
  location: "",
};

export function useCardForms() {
  const [editForm, setEditForm] = useState<ParentCardForm>(initialParentForm);
  const [childEditForm, setChildEditForm] = useState<ChildCardForm>(initialChildForm);

  const populateParentForm = useCallback((card: ExperienceCardV1 | ExperienceCard | (Record<string, unknown> & { id?: string })) => {
    const c = card as Record<string, unknown>;
    const loc = c.location as unknown;
    const locationStr =
      typeof loc === "string"
        ? loc
        : (loc && typeof loc === "object" && "text" in (loc as Record<string, unknown>) ? String((loc as Record<string, unknown>).text ?? "") : "");
    setEditForm({
      title: (c.title as string) ?? (c.headline as string) ?? "",
      summary: (c.context as string) ?? (c.summary as string) ?? "",
      normalized_role: (c.normalized_role as string) ?? (c.role_title as string) ?? "",
      domain: (c.domain as string) ?? "",
      sub_domain: (c.sub_domain as string) ?? "",
      company_name: (c.company_name as string) ?? (c.company as string) ?? "",
      company_type: (c.company_type as string) ?? "",
      location: locationStr,
      employment_type: (c.employment_type as string) ?? "",
      start_date: (c.start_date as string) ?? "",
      end_date: (c.end_date as string) ?? "",
      is_current: (c.is_current as boolean) ?? false,
      intent_primary: (c.intent_primary as string) ?? "",
      intent_secondary_str: Array.isArray(c.intent_secondary) ? (c.intent_secondary as unknown[]).map(String).join(", ") : "",
      seniority_level: (c.seniority_level as string) ?? "",
      confidence_score: c.confidence_score != null ? String(c.confidence_score) : "",
      experience_card_visibility: (c.experience_card_visibility as boolean) ?? true,
    });
  }, []);

  const populateChildForm = useCallback((child: ExperienceCardChild | (Record<string, unknown> & { id?: string })) => {
    const c = child as Record<string, unknown>;
    const tags = (c.tags as string[] | undefined) ?? [];
    setChildEditForm({
      title: (c.title as string) ?? (c.headline as string) ?? "",
      summary: (c.summary as string) ?? (c.context as string) ?? "",
      tagsStr: tags.join(", "),
      time_range: (c.time_range as string) ?? "",
      company: (c.company as string) ?? "",
      location: (c.location as string) ?? "",
    });
  }, []);

  return {
    editForm,
    setEditForm,
    childEditForm,
    setChildEditForm,
    populateParentForm,
    populateChildForm,
  };
}
