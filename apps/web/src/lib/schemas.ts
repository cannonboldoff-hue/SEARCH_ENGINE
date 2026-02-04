/**
 * Domain schemas: enums and core entities (Person, Experience Card v1).
 * Source of truth aligned with API spec.
 */

// -----------------------------------------------------------------------------
// 1.1 Enums
// -----------------------------------------------------------------------------

export const INTENTS = [
  "education",
  "work",
  "project",
  "achievement",
  "certification",
  "responsibility",
  "skill_application",
  "method_used",
  "artifact_created",
  "challenge",
  "decision",
  "learning",
  "life_event",
  "relocation",
  "volunteering",
  "community",
  "finance",
  "other",
  "mixed",
] as const;

export type Intent = (typeof INTENTS)[number];

export const CHILD_RELATION_TYPES = [
  "component_of",
  "skill_applied",
  "method_used",
  "tool_used",
  "artifact_created",
  "challenge_faced",
  "decision_made",
  "outcome_detail",
  "learning_from",
  "example_of",
] as const;

export type ChildRelationType = (typeof CHILD_RELATION_TYPES)[number];

export const VISIBILITY_VALUES = ["private", "profile_only", "searchable"] as const;

export type Visibility = (typeof VISIBILITY_VALUES)[number];

export const CLAIM_STATES = ["self_claim", "supported", "verified"] as const;

export type ClaimState = (typeof CLAIM_STATES)[number];

export const CONFIDENCE_LEVELS = ["high", "medium", "low"] as const;

export type Confidence = (typeof CONFIDENCE_LEVELS)[number];

export const REACTIONS = ["like", "respect", "insightful", "support", "curious"] as const;

export type Reaction = (typeof REACTIONS)[number];

// Verification
export const VERIFICATION_STATUS = ["unverified", "verified"] as const;

export type VerificationStatus = (typeof VERIFICATION_STATUS)[number];

export const VERIFICATION_METHODS = ["email_domain", "gov_id", "community", "document"] as const;

export type VerificationMethod = (typeof VERIFICATION_METHODS)[number];

// Evidence
export const EVIDENCE_TYPES = ["link", "file", "reference"] as const;

export type EvidenceType = (typeof EVIDENCE_TYPES)[number];

// Tool type (tooling.tools[].type)
export const TOOL_TYPES = ["software", "equipment", "system", "platform", "instrument", "other"] as const;

export type ToolType = (typeof TOOL_TYPES)[number];

// -----------------------------------------------------------------------------
// Entity taxonomy (for entities[].type)
// -----------------------------------------------------------------------------

export const ENTITY_TAXONOMY = [
  "person",
  "organization",
  "company",
  "school",
  "team",
  "community",
  "place",
  "event",
  "program",
  "domain",
  "industry",
  "product",
  "service",
  "artifact",
  "document",
  "portfolio_item",
  "credential",
  "award",
  "tool",
  "equipment",
  "system",
  "platform",
  "instrument",
  "method",
  "process",
] as const;

export type EntityType = (typeof ENTITY_TAXONOMY)[number];

// -----------------------------------------------------------------------------
// 1.2 Core entities – nested types
// -----------------------------------------------------------------------------

export type LocationBasic = {
  city: string | null;
  region: string | null;
  country: string | null;
};

export type PersonVerification = {
  status: VerificationStatus;
  methods: VerificationMethod[];
};

export type PersonPrivacyDefaults = {
  default_visibility: Visibility;
};

/** Person (user profile) */
export type Person = {
  person_id: string;
  username: string;
  display_name: string;
  photo_url: string | null;
  bio: string | null;
  location: LocationBasic;
  verification: PersonVerification;
  privacy_defaults: PersonPrivacyDefaults;
  created_at: string; // ISO-8601
  updated_at: string; // ISO-8601
};

// --- Experience Card v1 nested types ---

export type LanguageField = {
  raw_text: string | null;
  confidence: Confidence;
};

export type TimeField = {
  start: string | null; // YYYY-MM | YYYY-MM-DD
  end: string | null;
  ongoing: boolean | null;
  text: string | null;
  confidence: Confidence;
};

export type LocationWithConfidence = LocationBasic & {
  text: string | null;
  confidence: Confidence;
};

export type RoleItem = {
  label: string;
  seniority: string | null;
  confidence: Confidence;
};

export type ActionItem = {
  verb: string;
  verb_raw: string | null;
  confidence: Confidence;
};

export type TopicItem = {
  label: string;
  raw: string | null;
  confidence: Confidence;
};

export type EntityItem = {
  type: EntityType | string;
  name: string;
  entity_id: string | null;
  confidence: Confidence;
};

export type ToolItem = {
  name: string;
  type: ToolType;
  confidence: Confidence;
};

export type ProcessItem = {
  name: string;
  confidence: Confidence;
};

export type ToolingField = {
  tools: ToolItem[];
  processes: ProcessItem[];
  raw: string | null;
};

export type OutcomeItem = {
  type: string;
  label: string;
  value_text: string | null;
  metric: {
    name: string | null;
    value: number | null;
    unit: string | null;
  };
  confidence: Confidence;
};

export type EvidenceItem = {
  type: EvidenceType;
  url: string | null;
  note: string | null;
  visibility: Visibility;
};

export type PrivacyField = {
  visibility: Visibility;
  sensitive: boolean;
};

export type QualityField = {
  overall_confidence: Confidence;
  claim_state: ClaimState;
  needs_clarification: boolean;
  clarifying_question: string | null;
};

export type IndexField = {
  search_phrases: string[];
  embedding_ref: string | null;
};

/** Experience Card v1 (universal content unit). Parent: parent_id=null, depth=0, relation_type=null. Child: parent_id set, depth≥1, relation_type enum. */
export type ExperienceCardV1 = {
  id: string;
  person_id: string;
  created_by: string;
  version: 1;
  edited_at: string | null; // ISO-8601
  parent_id: string | null;
  depth: number;
  relation_type: ChildRelationType | string | null;
  intent: Intent;
  headline: string;
  summary: string;
  raw_text: string;
  language: LanguageField;
  time: TimeField;
  location: LocationWithConfidence;
  roles: RoleItem[];
  actions: ActionItem[];
  topics: TopicItem[];
  entities: EntityItem[];
  tooling: ToolingField;
  outcomes: OutcomeItem[];
  evidence: EvidenceItem[];
  privacy: PrivacyField;
  quality: QualityField;
  index: IndexField;
  created_at: string; // ISO-8601
  updated_at: string; // ISO-8601
};
