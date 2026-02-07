import { cn } from "@/lib/utils";
import type { ExperienceCardV1 } from "@/types";

function v1CardTopics(card: ExperienceCardV1): string[] {
  return (card.topics ?? []).map((t) => (typeof t === "object" && t && "label" in t ? t.label : String(t)));
}

/** Renders ExperienceCardV1 fields that have values; empty fields are not shown. */
export function V1CardDetails({ card, compact = false, summaryFullWidth = false }: { card: ExperienceCardV1; compact?: boolean; summaryFullWidth?: boolean }) {
  if (!card) return null;
  const topicLabels = v1CardTopics(card);
  const timeObj = card?.time && typeof card.time === "object" ? card.time as { text?: string; start?: string; end?: string; ongoing?: boolean } : null;
  const timeText = timeObj?.text ?? (timeObj ? [timeObj.start, timeObj.end].filter(Boolean).join(" – ") || (timeObj.ongoing ? "Ongoing" : null) : null);
  const roles = (card.roles ?? []).map((r) => typeof r === "object" && r && "label" in r ? (r as { label: string }).label : String(r));
  const actions = (card.actions ?? []).map((a) => typeof a === "object" && a && "verb" in a ? (a as { verb: string }).verb : String(a));
  const entities = (card.entities ?? []).map((e) => typeof e === "object" && e && "name" in e ? `${(e as { type?: string }).type ?? "entity"}: ${(e as { name: string }).name}` : String(e));
  const tools = (card.tooling?.tools ?? []).map((t) => typeof t === "object" && t && "name" in t ? (t as { name: string }).name : String(t));
  const processes = (card.tooling?.processes ?? []).map((p) => typeof p === "object" && p && "name" in p ? (p as { name: string }).name : String(p));
  const outcomes = (card.outcomes ?? []).map((o) => {
    if (typeof o !== "object" || !o) return null;
    const oo = o as { label?: string; value_text?: string | null; metric?: { name?: string | null; value?: number | null; unit?: string | null } };
    const parts = [oo.label, oo.value_text].filter(Boolean);
    if (oo.metric?.name != null || oo.metric?.value != null) {
      parts.push([oo.metric.name, oo.metric.value, oo.metric.unit].filter(Boolean).join(" "));
    }
    return parts.length ? parts.join(": ") : null;
  }).filter(Boolean) as string[];
  const evidence = (card.evidence ?? []).map((e) => {
    if (typeof e !== "object" || !e) return null;
    const ee = e as { type?: string; url?: string | null; note?: string | null };
    return [ee.type, ee.url ?? ee.note].filter(Boolean).join(": ");
  }).filter(Boolean) as string[];
  const intent = card.intent != null && String(card.intent) !== "" ? String(card.intent).replace(/_/g, " ") : null;
  const summaryText = (card.summary ?? "").toString().trim() || null;
  const lang = card.language && typeof card.language === "object" ? (card.language as { raw_text?: string; confidence?: string }).raw_text ?? (card.language as { confidence?: string }).confidence : null;
  const langStr = (lang ?? "").toString().trim() || null;
  const privacy = card.privacy && typeof card.privacy === "object" ? `${(card.privacy as { visibility?: string }).visibility ?? ""}${(card.privacy as { sensitive?: boolean }).sensitive ? ", sensitive" : ""}`.trim() || null : null;
  const quality = card.quality && typeof card.quality === "object"
    ? [`confidence: ${(card.quality as { overall_confidence?: string }).overall_confidence}`, `claim: ${(card.quality as { claim_state?: string }).claim_state}`, (card.quality as { needs_clarification?: boolean }).needs_clarification ? "needs clarification" : "", (card.quality as { clarifying_question?: string | null }).clarifying_question ?? ""].filter(Boolean).join("; ").trim() || null
    : null;
  const indexPhrases = (card.index?.search_phrases ?? []).length ? (card.index?.search_phrases ?? []).join(", ") : null;
  const indexRef = (card.index?.embedding_ref ?? "").trim() || null;

  const labelClass = compact ? "text-[10px] uppercase tracking-wide text-muted-foreground" : "text-xs font-medium text-muted-foreground";
  const valueClass = compact ? "text-xs" : "text-sm";

  function Row({ label, value }: { label: string; value: React.ReactNode }) {
    if (value == null || value === "") return null;
    return (
      <div className="min-w-0">
        <span className={labelClass}>{label}</span>
        <p className={cn(valueClass, "break-words")}>{value}</p>
      </div>
    );
  }

  const toolingValue =
    tools.length || processes.length || (card.tooling?.raw ?? "").trim()
      ? [...tools, ...processes].filter(Boolean).join(", ") + ((card.tooling?.raw ?? "").trim() ? ` — ${card.tooling?.raw?.trim()}` : "")
      : null;
  const createdAt = (card.created_at ?? "").toString().trim() || null;
  const updatedAt = (card.updated_at ?? "").toString().trim() || null;
  const personId = (card.person_id ?? "").toString().trim() || null;
  const createdBy = (card.created_by ?? "").toString().trim() || null;

  const cardAny = card as Record<string, unknown>;
  const constraintsStr = (cardAny.constraints as string)?.trim() || null;
  const decisionsStr = (cardAny.decisions as string)?.trim() || null;
  const outcomeStr = (cardAny.outcome as string)?.trim() || null;
  const teamStr = (cardAny.team as string)?.trim() || null;
  const timeRangeStr = (cardAny.time_range as string)?.trim() || null;
  const roleTitleStr = (cardAny.role_title as string)?.trim() || null;
  const companyStr = (cardAny.company as string)?.trim() || null;
  const domainStr = (cardAny.domain as string)?.trim() || null;
  const subDomainStr = (cardAny.sub_domain as string)?.trim() || null;
  const companyTypeStr = (cardAny.company_type as string)?.trim() || null;
  const employmentTypeStr = (cardAny.employment_type as string)?.trim() || null;
  const intentPrimaryStr = (cardAny.intent_primary as string)?.trim() || null;
  const intentSecondaryStr =
    Array.isArray(cardAny.intent_secondary) && (cardAny.intent_secondary as unknown[]).length
      ? (cardAny.intent_secondary as unknown[]).map(String).map((s) => s.trim()).filter(Boolean).join(", ")
      : null;
  const seniorityStr = (cardAny.seniority_level as string)?.trim() || null;
  const confidenceScore =
    typeof cardAny.confidence_score === "number" ? String(cardAny.confidence_score) : null;
  const visibilityStr =
    typeof cardAny.experience_card_visibility === "boolean" ? (cardAny.experience_card_visibility ? "Visible" : "Hidden") : null;

  const rows = [
    card.parent_id != null && card.parent_id !== "" && { label: "Parent ID", value: card.parent_id },
    card.depth != null && { label: "Depth", value: String(card.depth) },
    card.relation_type != null && card.relation_type !== "" && { label: "Relation type", value: String(card.relation_type).replace(/_/g, " ") },
    intent && { label: "Intent", value: intent },
    summaryText && { label: "Summary", value: summaryText },
    (timeText || timeRangeStr) && { label: "Time", value: timeText || timeRangeStr },
    roleTitleStr && { label: "Role", value: roleTitleStr },
    companyStr && { label: "Company", value: companyStr },
    companyTypeStr && { label: "Company type", value: companyTypeStr },
    teamStr && { label: "Team", value: teamStr },
    domainStr && { label: "Domain", value: domainStr },
    subDomainStr && { label: "Sub-domain", value: subDomainStr },
    employmentTypeStr && { label: "Employment", value: employmentTypeStr },
    constraintsStr && { label: "Constraints", value: constraintsStr },
    decisionsStr && { label: "Decisions", value: decisionsStr },
    outcomeStr && { label: "Outcome", value: outcomeStr },
    intentPrimaryStr && { label: "Intent (primary)", value: intentPrimaryStr },
    intentSecondaryStr && { label: "Intent (secondary)", value: intentSecondaryStr },
    seniorityStr && { label: "Seniority", value: seniorityStr },
    confidenceScore && { label: "Confidence score", value: confidenceScore },
    visibilityStr && { label: "Visibility", value: visibilityStr },
    langStr && { label: "Language", value: langStr },
    roles.length > 0 && { label: "Roles", value: roles.join(", ") },
    actions.length > 0 && { label: "Actions", value: actions.join(", ") },
    topicLabels.length > 0 && { label: "Topics", value: topicLabels.join(", ") },
    entities.length > 0 && { label: "Entities", value: entities.join(", ") },
    toolingValue && { label: "Tooling", value: toolingValue },
    outcomes.length > 0 && { label: "Outcomes", value: outcomes.join("; ") },
    evidence.length > 0 && { label: "Evidence", value: evidence.join("; ") },
    privacy && { label: "Privacy", value: privacy },
    quality && { label: "Quality", value: quality },
    indexPhrases && { label: "Search phrases", value: indexPhrases },
    indexRef && { label: "Embedding ref", value: indexRef },
    createdAt && { label: "Created at", value: createdAt },
    updatedAt && { label: "Updated at", value: updatedAt },
    card.edited_at != null && card.edited_at !== "" && { label: "Edited at", value: card.edited_at },
    personId && { label: "Person ID", value: personId },
    createdBy && { label: "Created by", value: createdBy },
    card.version != null && { label: "Version", value: String(card.version) },
  ].filter((r): r is { label: string; value: string } =>
    typeof r === "object" && r !== null && "value" in r && r.value != null && r.value !== ""
  );

  if (rows.length === 0) return null;

  const totalChars = rows.reduce((sum, row) => sum + `${row.label}${row.value}`.length, 0);
  const useTwoColumnCompact = compact && rows.length <= 6 && totalChars <= 220;
  const useTwoColumnFull = !compact && rows.length <= 8 && totalChars <= 320;

  if (summaryFullWidth) {
    const summaryRow = rows.find((r) => r.label === "Summary");
    const restRows = rows.filter((r) => r.label !== "Summary");
    return (
      <div className="mt-3 pt-3 border-t border-border/40 space-y-3">
        {summaryRow && (
          <div className="min-w-0">
            <Row key={`${summaryRow.label}-0`} label={summaryRow.label} value={summaryRow.value} />
          </div>
        )}
        {restRows.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
            {restRows.map((r, i) => (
              <Row key={`${r.label}-${i}`} label={r.label} value={r.value} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        compact
          ? useTwoColumnCompact
            ? "mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5"
            : "mt-2 space-y-1.5"
          : useTwoColumnFull
            ? "mt-3 pt-3 border-t border-border/40 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2"
            : "space-y-2 mt-3 pt-3 border-t border-border/40"
      )}
    >
      {rows.map((r, i) => (
        <Row key={`${r.label}-${i}`} label={r.label} value={r.value} />
      ))}
    </div>
  );
}

export { v1CardTopics };
