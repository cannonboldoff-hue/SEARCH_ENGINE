/** API / domain types shared across the app */

import type { ExperienceCardV1 } from "@/lib/schemas";

// Re-export domain schemas and enums from @/lib/schemas for use across the app
export {
  INTENTS,
  CHILD_RELATION_TYPES,
  VISIBILITY_VALUES,
  CLAIM_STATES,
  CONFIDENCE_LEVELS,
  REACTIONS,
  ENTITY_TAXONOMY,
  VERIFICATION_STATUS,
  VERIFICATION_METHODS,
  EVIDENCE_TYPES,
  TOOL_TYPES,
} from "@/lib/schemas";
export type {
  Intent,
  ChildRelationType,
  Visibility,
  ClaimState,
  Confidence,
  Reaction,
  EntityType,
  Person,
  ExperienceCardV1,
  LocationBasic,
  PersonVerification,
  PersonPrivacyDefaults,
  LanguageField,
  TimeField,
  LocationWithConfidence,
  RoleItem,
  ActionItem,
  TopicItem,
  EntityItem,
  ToolItem,
  ProcessItem,
  ToolingField,
  OutcomeItem,
  EvidenceItem,
  PrivacyField,
  QualityField,
  IndexField,
} from "@/lib/schemas";

export type PersonSearchResult = {
  id: string;
  name: string | null;
  headline: string | null;
  bio: string | null;
  similarity_percent?: number | null;
  why_matched?: string[];
  open_to_work: boolean;
  open_to_contact: boolean;
  work_preferred_locations: string[];
  work_preferred_salary_min: number | null;
  matched_cards: ExperienceCard[];
};

/** One person in the discover grid (GET /people). */
export type PersonListItem = {
  id: string;
  display_name: string | null;
  current_location: string | null;
  experience_summaries: string[];
};

export type PersonListResponse = {
  people: PersonListItem[];
};

/** Public profile for person detail page (GET /people/:id/profile). */
export type PersonPublicProfile = {
  id: string;
  display_name: string | null;
  bio: BioResponse | null;
  card_families: { parent: ExperienceCard; children: ExperienceCardChild[] }[];
};

export type SearchResponse = {
  search_id: string;
  people: PersonSearchResult[];
};

/** Response shape from GET `/me/experience-cards` and POST/PATCH `/experience-cards`. Matches backend `ExperienceCardResponse`. */
export type ExperienceCard = {
  id: string;
  user_id: string;
  title: string | null;
  normalized_role: string | null;
  domain: string | null;
  sub_domain: string | null;
  company_name: string | null;
  company_type: string | null;
  start_date: string | null; // YYYY-MM-DD
  end_date: string | null; // YYYY-MM-DD
  is_current: boolean | null;
  location: string | null;
  employment_type: string | null;
  summary: string | null;
  raw_text: string | null;
  intent_primary: string | null;
  intent_secondary: string[];
  seniority_level: string | null;
  confidence_score: number | null;
  experience_card_visibility: boolean;
  created_at: string | null;
  updated_at: string | null;
};

/** Request body for POST `/experience-cards` (create). Matches backend `ExperienceCardCreate`. */
export type ExperienceCardCreate = {
  title?: string | null;
  normalized_role?: string | null;
  domain?: string | null;
  sub_domain?: string | null;
  company_name?: string | null;
  company_type?: string | null;
  start_date?: string | null; // YYYY-MM-DD
  end_date?: string | null; // YYYY-MM-DD
  is_current?: boolean | null;
  location?: string | null;
  employment_type?: string | null;
  summary?: string | null;
  raw_text?: string | null;
  intent_primary?: string | null;
  intent_secondary?: string[] | null;
  seniority_level?: string | null;
  confidence_score?: number | null;
  experience_card_visibility?: boolean | null;
};

/** Request body for PATCH `/experience-cards/:card_id`. Matches backend `ExperienceCardPatch`. */
export type ExperienceCardPatch = {
  title?: string | null;
  normalized_role?: string | null;
  domain?: string | null;
  sub_domain?: string | null;
  company_name?: string | null;
  company_type?: string | null;
  start_date?: string | null; // YYYY-MM-DD
  end_date?: string | null; // YYYY-MM-DD
  is_current?: boolean | null;
  location?: string | null;
  employment_type?: string | null;
  summary?: string | null;
  raw_text?: string | null;
  intent_primary?: string | null;
  intent_secondary?: string[] | null;
  seniority_level?: string | null;
  confidence_score?: number | null;
  experience_card_visibility?: boolean | null;
};

export type ContactDetails = {
  email_visible: boolean;
  email?: string | null;
  phone: string | null;
  linkedin_url: string | null;
  other: string | null;
};

export type PersonProfile = {
  id: string;
  display_name: string | null;
  open_to_work: boolean;
  open_to_contact: boolean;
  work_preferred_locations: string[];
  work_preferred_salary_min: number | null;
  experience_cards: ExperienceCard[];
  /** Full experience card families (parent + children) for search profile view. */
  card_families?: { parent: ExperienceCard; children: ExperienceCardChild[] }[];
  /** Bio when viewing from search (same as public profile). */
  bio?: BioResponse | null;
  contact: ContactDetails | null;
};

/** One parent Experience Card v1 + its children. Matches backend CardFamilyV1Response. */
export type CardFamilyV1Response = {
  parent: ExperienceCardV1;
  children: ExperienceCardV1[];
};

/** Result of POST /experience-cards/draft-v1. Matches backend DraftSetV1Response. */
export type DraftSetV1Response = {
  draft_set_id: string;
  raw_experience_id: string;
  card_families: CardFamilyV1Response[];
};

/** Result of POST /experiences/rewrite. Matches backend RewriteTextResponse. */
export type RewriteTextResponse = {
  rewritten_text: string;
};

/** Patch body for PATCH `/experience-card-children/:child_id`. Matches backend `ExperienceCardChildPatch`. */
export type ExperienceCardChildPatch = {
  title?: string | null;
  summary?: string | null;
  tags?: string[] | null;
  time_range?: string | null;
  company?: string | null;
  location?: string | null;
};

/** Response DTO for child cards (draft-v1 compatible). Matches backend `ExperienceCardChildResponse`. */
export type ExperienceCardChild = {
  id: string;
  relation_type?: string | null;
  title: string;
  context: string;
  tags: string[];
  headline: string;
  summary: string;
  topics: { label: string }[];
  time_range: string | null;
  role_title: string | null;
  company: string | null;
  location: string | null;
};

/** One parent + children from GET /me/experience-card-families. Matches backend CardFamilyResponse. */
export type SavedCardFamily = {
  parent: ExperienceCard;
  children: ExperienceCardChild[];
};

export type BioResponse = {
  first_name: string | null;
  last_name: string | null;
  date_of_birth: string | null;
  current_city: string | null;
  profile_photo_url: string | null;
  school: string | null;
  college: string | null;
  current_company: string | null;
  past_companies: { company_name: string; role?: string; years?: string }[] | null;
  email: string | null;
  linkedin_url: string | null;
  phone: string | null;
  complete: boolean;
};

export type VisibilitySettingsResponse = {
  open_to_work: boolean;
  work_preferred_locations: string[];
  work_preferred_salary_min: number | null;
  open_to_contact: boolean;
};

export type PatchVisibilityRequest = {
  open_to_work?: boolean;
  work_preferred_locations?: string[];
  work_preferred_salary_min?: number | null;
  open_to_contact?: boolean;
};
