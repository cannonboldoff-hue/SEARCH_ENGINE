import { cn } from "@/lib/utils";
import type { ExperienceCardV1 } from "@/types";

function toText(value: unknown): string | null {
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

export function v1CardTopics(card: ExperienceCardV1 | Record<string, unknown>): string[] {
  const topics = (card as Record<string, unknown>).topics;
  if (!Array.isArray(topics)) return [];
  return topics
    .map((t) =>
      typeof t === "object" && t && "label" in t
        ? String((t as { label?: unknown }).label ?? "")
        : String(t)
    )
    .filter(Boolean);
}

/** Labels to hide when hideInternalFields is true (read-only display, no metadata). */
const INTERNAL_FIELD_LABELS = new Set([
  "Parent ID", "Depth", "Confidence score", "Visibility", "Created at", "Updated at",
  "Edited at", "Person ID", "Created by", "Version", "Embedding ref", "Search phrases",
  "Privacy", "Quality", "Intent", "Intent (primary)", "Intent (secondary)",
]);

/** Renders card fields that have values; empty fields are not shown. */
export function V1CardDetails({
  card,
  compact = false,
  summaryFullWidth = false,
  hideInternalFields = false,
}: {
  card: ExperienceCardV1 | Record<string, unknown>;
  compact?: boolean;
  summaryFullWidth?: boolean;
  /** When true, omit metadata/internal rows (created at, visibility, intent, etc.) for read-only display. */
  hideInternalFields?: boolean;
}) {
  if (!card) return null;

  const cardAny = card as Record<string, unknown>;
  const topicLabels = v1CardTopics(cardAny);

  const timeObj =
    cardAny.time && typeof cardAny.time === "object"
      ? (cardAny.time as { text?: unknown; start?: unknown; end?: unknown; ongoing?: unknown })
      : null;
  const startDateStr = toText(cardAny.start_date);
  const endDateStr = toText(cardAny.end_date);
  const timeRangeStr = toText(cardAny.time_range);
  const isCurrent = typeof cardAny.is_current === "boolean" ? cardAny.is_current : false;
  const timeObjRange = [toText(timeObj?.start), toText(timeObj?.end)].filter(Boolean).join(" - ");
  const timeTextFromObj = toText(timeObj?.text) || timeObjRange || (timeObj?.ongoing === true ? "Ongoing" : null);
  const dateRange = [startDateStr, endDateStr].filter(Boolean).join(" - ");
  const timeText = timeTextFromObj || timeRangeStr || dateRange || (isCurrent ? "Ongoing" : null);

  const roles = (Array.isArray(cardAny.roles) ? cardAny.roles : [])
    .map((r) =>
      typeof r === "object" && r && "label" in r
        ? String((r as { label?: unknown }).label ?? "")
        : String(r)
    )
    .filter(Boolean);

  const actions = (Array.isArray(cardAny.actions) ? cardAny.actions : [])
    .map((a) =>
      typeof a === "object" && a && "verb" in a
        ? String((a as { verb?: unknown }).verb ?? "")
        : String(a)
    )
    .filter(Boolean);

  const entities = (Array.isArray(cardAny.entities) ? cardAny.entities : [])
    .map((e) =>
      typeof e === "object" && e && "name" in e
        ? `${(e as { type?: unknown }).type ?? "entity"}: ${(e as { name?: unknown }).name ?? ""}`
        : String(e)
    )
    .filter(Boolean);

  const toolingObj =
    cardAny.tooling && typeof cardAny.tooling === "object"
      ? (cardAny.tooling as { tools?: unknown; processes?: unknown; raw?: unknown })
      : null;

  const tools = (Array.isArray(toolingObj?.tools) ? toolingObj?.tools : [])
    .map((t) =>
      typeof t === "object" && t && "name" in t
        ? String((t as { name?: unknown }).name ?? "")
        : String(t)
    )
    .filter(Boolean);

  const processes = (Array.isArray(toolingObj?.processes) ? toolingObj?.processes : [])
    .map((p) =>
      typeof p === "object" && p && "name" in p
        ? String((p as { name?: unknown }).name ?? "")
        : String(p)
    )
    .filter(Boolean);

  const outcomes = (Array.isArray(cardAny.outcomes) ? cardAny.outcomes : [])
    .map((o) => {
      if (typeof o !== "object" || !o) return null;
      const oo = o as { label?: string; value_text?: string | null };
      const parts = [oo.label, oo.value_text].filter(Boolean);
      return parts.length ? parts.join(": ") : null;
    })
    .filter(Boolean) as string[];

  const evidence = (Array.isArray(cardAny.evidence) ? cardAny.evidence : [])
    .map((e) => {
      if (typeof e !== "object" || !e) return null;
      const ee = e as { type?: string; url?: string | null; note?: string | null };
      return [ee.type, ee.url ?? ee.note].filter(Boolean).join(": ");
    })
    .filter(Boolean) as string[];

  const intentSource = toText(cardAny.intent) ?? toText(cardAny.intent_primary);
  const intent = intentSource ? intentSource.replace(/_/g, " ") : null;
  const summaryText = toText(cardAny.summary) ?? toText(cardAny.context);

  const locationValue = cardAny.location;
  const locationObj =
    locationValue && typeof locationValue === "object"
      ? (locationValue as { text?: unknown; city?: unknown; region?: unknown; country?: unknown })
      : null;
  const locationRange = [toText(locationObj?.city), toText(locationObj?.region), toText(locationObj?.country)]
    .filter(Boolean)
    .join(", ");
  const locationStr = toText(locationValue) || toText(locationObj?.text) || locationRange || null;

  const lang =
    cardAny.language && typeof cardAny.language === "object"
      ? (cardAny.language as { raw_text?: unknown; confidence?: unknown }).raw_text ??
        (cardAny.language as { confidence?: unknown }).confidence
      : null;
  const langStr = toText(lang);

  const privacy =
    cardAny.privacy && typeof cardAny.privacy === "object"
      ? `${toText((cardAny.privacy as { visibility?: unknown }).visibility) ?? ""}${
          (cardAny.privacy as { sensitive?: unknown }).sensitive === true ? ", sensitive" : ""
        }`.trim() || null
      : null;

  const quality =
    cardAny.quality && typeof cardAny.quality === "object"
      ? [
          `confidence: ${toText((cardAny.quality as { overall_confidence?: unknown }).overall_confidence)}`,
          `claim: ${toText((cardAny.quality as { claim_state?: unknown }).claim_state)}`,
          (cardAny.quality as { needs_clarification?: unknown }).needs_clarification === true
            ? "needs clarification"
            : "",
          toText((cardAny.quality as { clarifying_question?: unknown }).clarifying_question),
        ]
          .filter(Boolean)
          .join("; ")
          .trim() || null
      : null;

  const indexObj =
    cardAny.index && typeof cardAny.index === "object"
      ? (cardAny.index as { search_phrases?: unknown; embedding_ref?: unknown })
      : null;
  const indexPhrases =
    Array.isArray(indexObj?.search_phrases) && indexObj.search_phrases.length
      ? indexObj.search_phrases.map(String).join(", ")
      : null;
  const indexRef = toText(indexObj?.embedding_ref);

  const labelClass = compact
    ? "text-[10px] uppercase tracking-wide text-muted-foreground"
    : "text-xs font-medium text-muted-foreground";
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

  const toolingRaw = toText(toolingObj?.raw);
  const toolingList = [...tools, ...processes].filter(Boolean).join(", ");
  const toolingValue =
    tools.length || processes.length || toolingRaw
      ? `${toolingList}${toolingRaw ? `${toolingList ? " - " : ""}${toolingRaw}` : ""}`
      : null;

  const createdAt = toText(cardAny.created_at);
  const updatedAt = toText(cardAny.updated_at);
  const personId = toText(cardAny.person_id);
  const createdBy = toText(cardAny.created_by);

  const constraintsStr = toText(cardAny.constraints);
  const decisionsStr = toText(cardAny.decisions);
  const outcomeStr = toText(cardAny.outcome);
  const teamStr = toText(cardAny.team);
  const roleTitleStr = toText(cardAny.role_title) ?? toText(cardAny.normalized_role);
  const companyStr = toText(cardAny.company) ?? toText(cardAny.company_name);
  const domainStr = toText(cardAny.domain);
  const subDomainStr = toText(cardAny.sub_domain);
  const companyTypeStr = toText(cardAny.company_type);
  const employmentTypeStr = toText(cardAny.employment_type);
  const intentPrimaryStr = toText(cardAny.intent_primary);
  const intentSecondaryStr =
    Array.isArray(cardAny.intent_secondary) && (cardAny.intent_secondary as unknown[]).length
      ? (cardAny.intent_secondary as unknown[])
          .map(String)
          .map((s) => s.trim())
          .filter(Boolean)
          .join(", ")
      : null;
  const seniorityStr = toText(cardAny.seniority_level);
  const confidenceScore = toText(cardAny.confidence_score);
  const visibilityStr =
    typeof cardAny.experience_card_visibility === "boolean"
      ? cardAny.experience_card_visibility
        ? "Visible"
        : "Hidden"
      : null;
  const parentId = toText(cardAny.parent_id);
  const depth = typeof cardAny.depth === "number" ? String(cardAny.depth) : null;
  const editedAt = toText(cardAny.edited_at);
  const version = typeof cardAny.version === "number" ? String(cardAny.version) : null;

  const rows = [
    parentId && { label: "Parent ID", value: parentId },
    depth && { label: "Depth", value: depth },
    intent && { label: "Intent", value: intent },
    summaryText && { label: "Summary", value: summaryText },
    timeText && { label: "Time", value: timeText },
    roleTitleStr && { label: "Role", value: roleTitleStr },
    companyStr && { label: "Company", value: companyStr },
    companyTypeStr && { label: "Company type", value: companyTypeStr },
    teamStr && { label: "Team", value: teamStr },
    locationStr && { label: "Location", value: locationStr },
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
    editedAt && { label: "Edited at", value: editedAt },
    personId && { label: "Person ID", value: personId },
    createdBy && { label: "Created by", value: createdBy },
    version && { label: "Version", value: version },
  ].filter(
    (r): r is { label: string; value: string } =>
      typeof r === "object" && r !== null && "value" in r && r.value != null && r.value !== ""
  );

  const filteredRows = hideInternalFields
    ? rows.filter((r) => !INTERNAL_FIELD_LABELS.has(r.label))
    : rows;

  if (filteredRows.length === 0) return null;

  const totalChars = filteredRows.reduce((sum, row) => sum + `${row.label}${row.value}`.length, 0);
  const useTwoColumnCompact = compact && filteredRows.length <= 6 && totalChars <= 220;
  const useTwoColumnFull = !compact && filteredRows.length <= 8 && totalChars <= 320;

  if (summaryFullWidth) {
    const summaryRow = filteredRows.find((r) => r.label === "Summary");
    const restRows = filteredRows.filter((r) => r.label !== "Summary");
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
      {filteredRows.map((r, i) => (
        <Row key={`${r.label}-${i}`} label={r.label} value={r.value} />
      ))}
    </div>
  );
}
