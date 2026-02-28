import { useState, useCallback } from "react";
import type { ExperienceCard, ExperienceCardChild, ChildValueItem } from "@/types";

const MONTH_LOOKUP: Record<string, number> = {
  jan: 1,
  january: 1,
  feb: 2,
  february: 2,
  mar: 3,
  march: 3,
  apr: 4,
  april: 4,
  may: 5,
  jun: 6,
  june: 6,
  jul: 7,
  july: 7,
  aug: 8,
  august: 8,
  sep: 9,
  sept: 9,
  september: 9,
  oct: 10,
  october: 10,
  nov: 11,
  november: 11,
  dec: 12,
  december: 12,
};

const pad2 = (n: number) => (n < 10 ? `0${n}` : String(n));

function normalizeDateInput(value: unknown): string {
  if (value == null) return "";
  const raw = String(value).trim();
  if (!raw) return "";

  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;

  const yearMonthMatch = raw.match(/^(\d{4})-(\d{2})$/);
  if (yearMonthMatch) return `${yearMonthMatch[1]}-${yearMonthMatch[2]}-01`;

  const monthYearMatch = raw.match(/^([A-Za-z]{3,9})\s+(\d{4})$/);
  if (monthYearMatch) {
    const month = MONTH_LOOKUP[monthYearMatch[1].toLowerCase()];
    if (month) return `${monthYearMatch[2]}-${pad2(month)}-01`;
  }

  const yearMonthNameMatch = raw.match(/^(\d{4})\s+([A-Za-z]{3,9})$/);
  if (yearMonthNameMatch) {
    const month = MONTH_LOOKUP[yearMonthNameMatch[2].toLowerCase()];
    if (month) return `${yearMonthNameMatch[1]}-${pad2(month)}-01`;
  }

  const numericMonthYearMatch = raw.match(/^(\d{1,2})[\/.-](\d{4})$/);
  if (numericMonthYearMatch) {
    const month = Number(numericMonthYearMatch[1]);
    if (month >= 1 && month <= 12) return `${numericMonthYearMatch[2]}-${pad2(month)}-01`;
  }

  return "";
}

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
  items: ChildValueItem[];
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
  items: [],
};

export function useCardForms() {
  const [editForm, setEditForm] = useState<ParentCardForm>(initialParentForm);
  const [childEditForm, setChildEditForm] = useState<ChildCardForm>(initialChildForm);

  const populateParentForm = useCallback((card: ExperienceCard | (Record<string, unknown> & { id?: string })) => {
    const c = card as Record<string, unknown>;
    const time = (c.time && typeof c.time === "object") ? (c.time as Record<string, unknown>) : null;
    const timeStart = typeof time?.start === "string" ? time.start : "";
    const timeEnd = typeof time?.end === "string" ? time.end : "";
    const timeOngoing = typeof time?.ongoing === "boolean" ? time.ongoing : undefined;
    const rawStart = (c.start_date as string) ?? "";
    const rawEnd = (c.end_date as string) ?? "";
    const startCandidate = rawStart && String(rawStart).trim() ? rawStart : timeStart;
    const endCandidate = rawEnd && String(rawEnd).trim() ? rawEnd : timeEnd;
    const isCurrent =
      typeof c.is_current === "boolean" ? (c.is_current as boolean) :
      typeof timeOngoing === "boolean" ? timeOngoing :
      false;
    const loc = c.location as unknown;
    const locationStr =
      typeof loc === "string"
        ? loc
        : (loc && typeof loc === "object" && "text" in (loc as Record<string, unknown>) ? String((loc as Record<string, unknown>).text ?? "") : "");
    setEditForm({
      title: (c.title as string) ?? "",
      summary: (c.summary as string) ?? "",
      normalized_role: (c.normalized_role as string) ?? "",
      domain: (c.domain as string) ?? "",
      sub_domain: (c.sub_domain as string) ?? "",
      company_name: (c.company_name as string) ?? (c.company as string) ?? "",
      company_type: (c.company_type as string) ?? "",
      location: locationStr,
      employment_type: (c.employment_type as string) ?? "",
      start_date: normalizeDateInput(startCandidate),
      end_date: normalizeDateInput(endCandidate),
      is_current: isCurrent,
      intent_primary: (c.intent_primary as string) ?? "",
      intent_secondary_str: Array.isArray(c.intent_secondary) ? (c.intent_secondary as unknown[]).map(String).join(", ") : "",
      seniority_level: (c.seniority_level as string) ?? "",
      confidence_score: c.confidence_score != null ? String(c.confidence_score) : "",
      experience_card_visibility: (c.experience_card_visibility as boolean) ?? true,
    });
  }, []);

  const populateChildForm = useCallback((child: ExperienceCardChild | (Record<string, unknown> & { id?: string })) => {
    const c = child as Record<string, unknown>;
    const items = (c.items as Record<string, unknown>[] | undefined) ?? [];
    const first = items[0];
    // API returns { title, description }; form uses { subtitle, sub_summary }
    const firstTitle = first ? String(first.subtitle ?? first.title ?? "").trim() : "";
    const firstSummary = first ? String(first.sub_summary ?? first.description ?? "").trim() : "";
    const formItems = items.length > 0
      ? items.map((it) => ({
          subtitle: String(it.subtitle ?? it.title ?? "").trim(),
          sub_summary: (it.sub_summary ?? it.description ?? null) as string | null,
        }))
      : [{ subtitle: "", sub_summary: null }];
    setChildEditForm({
      title: firstTitle || (c.child_type as string) || "",
      summary: firstSummary,
      items: formItems,
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
