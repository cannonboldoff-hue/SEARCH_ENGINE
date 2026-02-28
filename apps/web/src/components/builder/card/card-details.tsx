import { cn } from "@/lib/utils";
import type { ExperienceCard, ExperienceCardChild } from "@/types";
import { Briefcase, MapPin, Calendar, Wrench } from "lucide-react";

function toText(value: unknown): string | null {
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

/** Titles that indicate an empty/placeholder card; show fallback instead. */
const GENERIC_CARD_TITLES = new Set([
  "experience",
  "tools experience",
  "tools",
  "tools detail",
  "general experience",
  "unspecified experience",
]);

export function displayCardTitle(
  title: string | null | undefined,
  fallback = "Untitled"
): string {
  const t = (title ?? "").trim().toLowerCase();
  if (!t || GENERIC_CARD_TITLES.has(t)) return fallback;
  return (title ?? "").trim();
}

/** API returns items as { title, description }; frontend form uses { subtitle, sub_summary }. Accept both. */
function getFirstItemTitle(first: Record<string, unknown> | undefined): string {
  if (!first || typeof first !== "object") return "";
  const v = (first.subtitle ?? first.title ?? "").toString().trim();
  return v;
}

function getFirstItemSummary(first: Record<string, unknown> | undefined): string {
  if (!first || typeof first !== "object") return "";
  const v = (first.sub_summary ?? first.description ?? "").toString().trim();
  return v;
}

/** Derive display title from child (first item subtitle/title or child_type). */
export function getChildDisplayTitle(child: ExperienceCardChild | Record<string, unknown>): string {
  const c = child as Record<string, unknown>;
  const items = c.items as Record<string, unknown>[] | undefined;
  const first = items?.[0];
  const title = getFirstItemTitle(first);
  if (title) return title;
  return (c.child_type as string) || "";
}

/** All item titles from child, one per line. */
export function getChildDisplayTitlesAll(child: ExperienceCardChild | Record<string, unknown>): string {
  const c = child as Record<string, unknown>;
  const items = (c.items as Record<string, unknown>[] | undefined) ?? [];
  const titles = items
    .map((it) => getFirstItemTitle(it))
    .filter(Boolean);
  return titles.join("\n") || (c.child_type as string) || "";
}

/** All items from child formatted as "subtitle: description", one per line. Falls back to title-only or summary-only when the other is missing. */
export function getChildDisplayTitlesWithDescriptions(
  child: ExperienceCardChild | Record<string, unknown>
): string {
  const c = child as Record<string, unknown>;
  const items = (c.items as Record<string, unknown>[] | undefined) ?? [];
  const lines = items
    .map((it) => {
      const title = getFirstItemTitle(it);
      const summary = getFirstItemSummary(it);
      if (title && summary) return `${title}: ${summary}`;
      if (title) return title;
      if (summary) return summary;
      return "";
    })
    .filter(Boolean);
  return lines.join("\n") || (c.child_type as string) || "";
}

/** Child items as { title, summary } for styled rendering (e.g. description in muted color). */
export function getChildDisplayItems(
  child: ExperienceCardChild | Record<string, unknown>
): { title: string; summary: string }[] {
  const c = child as Record<string, unknown>;
  const items = (c.items as Record<string, unknown>[] | undefined) ?? [];
  return items
    .map((it) => ({
      title: getFirstItemTitle(it),
      summary: getFirstItemSummary(it),
    }))
    .filter((pair) => pair.title || pair.summary);
}

/** Derive display summary from child (first item sub_summary/description). */
export function getChildDisplaySummary(child: ExperienceCardChild | Record<string, unknown>): string {
  const c = child as Record<string, unknown>;
  const items = c.items as Record<string, unknown>[] | undefined;
  const first = items?.[0];
  return getFirstItemSummary(first);
}

/** True if child card has no meaningful content; such cards should not be shown. */
export function isPlaceholderChildCard(
  child: ExperienceCardChild | Record<string, unknown>
): boolean {
  const title = getChildDisplayTitle(child);
  const summary = getChildDisplaySummary(child);
  const items = (child as Record<string, unknown>).items as Record<string, unknown>[] | undefined;
  const hasItems = Array.isArray(items) && items.some((it) => getFirstItemTitle(it) || getFirstItemSummary(it));
  return !title && !summary && !hasItems;
}

/** Extract location string from card for display (e.g. in header row). */
export function getLocationFromCard(card: ExperienceCard | ExperienceCardChild | Record<string, unknown>): string | null {
  const cardAny = card as Record<string, unknown>;
  const locationValue = cardAny.location;
  const locationObj =
    locationValue && typeof locationValue === "object"
      ? (locationValue as { text?: unknown; city?: unknown; region?: unknown; country?: unknown })
      : null;
  const locationRange = [toText(locationObj?.city), toText(locationObj?.region), toText(locationObj?.country)]
    .filter(Boolean)
    .join(", ");
  const locationStrRaw = toText(locationValue) || toText(locationObj?.text) || locationRange || null;
  return locationStrRaw && locationStrRaw !== "{}" && locationStrRaw.trim() ? locationStrRaw.trim() : null;
}

export function cardTopics(card: ExperienceCard | ExperienceCardChild | Record<string, unknown>): string[] {
  const cardAny = card as Record<string, unknown>;
  const tags = cardAny.tags;
  if (Array.isArray(tags)) return tags.map(String).filter(Boolean);
  // Child cards: derive from items[].subtitle or items[].title (API returns title)
  const items = cardAny.items as Record<string, unknown>[] | undefined;
  if (Array.isArray(items)) return items.map((it) => String(it?.subtitle ?? it?.title ?? "")).filter(Boolean);
  const topics = cardAny.topics;
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

/** Renders card fields that have values; empty fields are not shown. Uses backend field names (ExperienceCardResponse / ExperienceCardChildResponse). */
export function CardDetails({
  card,
  compact = false,
  summaryFullWidth = false,
  hideInternalFields = false,
  expandSummary = false,
  hideSummary = false,
  hideTime = false,
  hideLocation = false,
}: {
  card: ExperienceCard | ExperienceCardChild | Record<string, unknown>;
  compact?: boolean;
  summaryFullWidth?: boolean;
  hideInternalFields?: boolean;
  /** When true, show full summary text without line clamp */
  expandSummary?: boolean;
  /** When true, do not render the summary paragraph */
  hideSummary?: boolean;
  /** When true, do not render the date/time in the meta row (e.g. when parent already shows it) */
  hideTime?: boolean;
  /** When true, do not render location in the meta row (e.g. when shown in header) */
  hideLocation?: boolean;
}) {
  if (!card) return null;

  const cardAny = card as Record<string, unknown>;
  const topicLabels = cardTopics(cardAny);

  const timeObj =
    cardAny.time && typeof cardAny.time === "object"
      ? (cardAny.time as { text?: unknown; start?: unknown; end?: unknown; ongoing?: unknown })
      : null;
  const startDateStr = toText(cardAny.start_date);
  const endDateStr = toText(cardAny.end_date);
  const timeRangeStr = toText(cardAny.time_range);
  const isCurrent = typeof cardAny.is_current === "boolean" ? cardAny.is_current : false;
  const timeObjRange = [toText(timeObj?.start), toText(timeObj?.end)].filter(Boolean).join(" – ");
  const timeTextFromObj = toText(timeObj?.text) || timeObjRange || (timeObj?.ongoing === true ? "Ongoing" : null);
  const dateRange = [startDateStr, endDateStr].filter(Boolean).join(" – ");
  const timeText = timeTextFromObj || timeRangeStr || dateRange || (isCurrent ? "Ongoing" : null);

  const summaryText =
    toText(cardAny.summary) ||
    (Array.isArray(cardAny.items) ? toText((cardAny.items as Record<string, unknown>[])[0]?.sub_summary ?? (cardAny.items as Record<string, unknown>[])[0]?.description) : null);

  const roleTitleStr = toText(cardAny.normalized_role);
  const companyStr = toText(cardAny.company_name) ?? toText(cardAny.company);

  const locationValue = cardAny.location;
  const locationObj =
    locationValue && typeof locationValue === "object"
      ? (locationValue as { text?: unknown; city?: unknown; region?: unknown; country?: unknown })
      : null;
  const locationRange = [toText(locationObj?.city), toText(locationObj?.region), toText(locationObj?.country)]
    .filter(Boolean)
    .join(", ");
  const locationStrRaw = toText(locationValue) || toText(locationObj?.text) || locationRange || null;
  const locationStr =
    locationStrRaw && locationStrRaw !== "{}" && locationStrRaw.trim()
      ? locationStrRaw.trim()
      : null;

  const domainStr = toText(cardAny.domain);
  const employmentTypeStr = toText(cardAny.employment_type);

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
  const toolingRaw = toText(toolingObj?.raw);
  const allTools = [...tools, ...processes].filter(Boolean);
  if (toolingRaw && allTools.length === 0) allTools.push(toolingRaw);

  const outcomes = (Array.isArray(cardAny.outcomes) ? cardAny.outcomes : [])
    .map((o) => {
      if (typeof o !== "object" || !o) return null;
      const oo = o as { label?: string; value_text?: string | null };
      const parts = [oo.label, oo.value_text].filter(Boolean);
      return parts.length ? parts.join(": ") : null;
    })
    .filter(Boolean) as string[];

  const metaItems: string[] = [];
  if (roleTitleStr) metaItems.push(roleTitleStr);
  if (companyStr) metaItems.push(companyStr);

  const tagItems: string[] = [];
  if (domainStr) tagItems.push(domainStr);
  if (employmentTypeStr) tagItems.push(employmentTypeStr.replace(/_/g, " "));
  topicLabels.forEach((t) => tagItems.push(t));

  const valueItems = Array.isArray((cardAny.value as { items?: unknown[] })?.items)
    ? ((cardAny.value as { items: Record<string, unknown>[] }).items)
    : Array.isArray(cardAny.items)
      ? (cardAny.items as Record<string, unknown>[])
      : null;
  const hasValueItems = valueItems && valueItems.length > 0;

  if (!hideInternalFields) {
    return <CardDetailsVerbose card={card} compact={compact} summaryFullWidth={summaryFullWidth} />;
  }

  const hasAnything =
    (summaryText && !hideSummary) ||
    metaItems.length > 0 ||
    timeText ||
    locationStr ||
    tagItems.length > 0 ||
    (hasValueItems ?? false);
  if (!hasAnything) return null;

  return (
    <div className={cn("mt-2.5 space-y-2", compact && "mt-1.5 space-y-1.5")}>
      {summaryText && !hideSummary && (
        <p className={cn(
          "text-sm text-muted-foreground leading-relaxed",
          !expandSummary && (compact ? "line-clamp-2" : "line-clamp-3")
        )}>
          {summaryText}
        </p>
      )}

      {(metaItems.length > 0 || (timeText && !hideTime) || (locationStr && !hideLocation)) && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {roleTitleStr && (
            <span className="inline-flex items-center gap-1">
              <Briefcase className="h-3 w-3 flex-shrink-0 opacity-60" />
              {roleTitleStr}
            </span>
          )}
          {locationStr && !hideLocation && (
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3 flex-shrink-0 opacity-60" />
              {locationStr}
            </span>
          )}
          {timeText && !hideTime && (
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3 w-3 flex-shrink-0 opacity-60" />
              {timeText}
            </span>
          )}
        </div>
      )}

      {hasValueItems ? (
        <div className="space-y-1">
          {valueItems!.map((it, i) => (
            <div key={i} className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{String(it.subtitle ?? it.title ?? "")}</span>
              {(it.sub_summary ?? it.description) ? (
                <span className="ml-1.5">— {String(it.sub_summary ?? it.description ?? "")}</span>
              ) : null}
            </div>
          ))}
        </div>
      ) : tagItems.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {tagItems.map((tag, i) => (
            <span
              key={`${tag}-${i}`}
              className="inline-flex items-center rounded-full bg-primary/8 px-2 py-0.5 text-[12px] font-medium text-primary/80"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}


      {allTools.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Wrench className="h-3 w-3 text-muted-foreground/50 flex-shrink-0" />
          {allTools.slice(0, 5).map((tool, i) => (
            <span
              key={`${tool}-${i}`}
              className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {tool}
            </span>
          ))}
          {allTools.length > 5 && (
            <span className="text-[11px] text-muted-foreground/60">+{allTools.length - 5}</span>
          )}
        </div>
      )}

      {outcomes.length > 0 && (
        <p className="text-xs text-muted-foreground/80 line-clamp-1">
          {outcomes.join(" · ")}
        </p>
      )}
    </div>
  );
}

function CardDetailsVerbose({
  card,
  compact = false,
  summaryFullWidth = false,
}: {
  card: ExperienceCard | ExperienceCardChild | Record<string, unknown>;
  compact?: boolean;
  summaryFullWidth?: boolean;
}) {
  if (!card) return null;

  const cardAny = card as Record<string, unknown>;
  const topicLabels = cardTopics(cardAny);

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
  const locationStrRaw = toText(locationValue) || toText(locationObj?.text) || locationRange || null;
  const locationStr =
    locationStrRaw && locationStrRaw !== "{}" && locationStrRaw.trim()
      ? locationStrRaw.trim()
      : null;

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
    if (value == null || value === "" || value === "{}") return null;
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
  const roleTitleStr = toText(cardAny.normalized_role) ?? toText(cardAny.role_title);
  const companyStr = toText(cardAny.company_name) ?? toText(cardAny.company);
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
  const parentIdStr = toText(cardAny.parent_id);
  const depth = typeof cardAny.depth === "number" ? String(cardAny.depth) : null;
  const editedAt = toText(cardAny.edited_at);
  const version = typeof cardAny.version === "number" ? String(cardAny.version) : null;

  const rows = [
    parentIdStr && { label: "Parent ID", value: parentIdStr },
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
