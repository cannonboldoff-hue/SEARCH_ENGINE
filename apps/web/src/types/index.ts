/** API / domain types shared across the app */

export type PersonSearchResult = {
  id: string;
  display_name: string | null;
  open_to_work: boolean;
  open_to_contact: boolean;
};

export type SearchResponse = {
  search_id: string;
  people: PersonSearchResult[];
};

export type ExperienceCard = {
  id: string;
  person_id?: string;
  raw_experience_id?: string | null;
  status: string;
  human_edited?: boolean;
  locked?: boolean;
  title: string | null;
  context: string | null;
  constraints: string | null;
  decisions: string | null;
  outcome: string | null;
  tags: string[];
  company: string | null;
  team: string | null;
  role_title: string | null;
  time_range: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ContactDetails = {
  email_visible: boolean;
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
  work_preferred_salary_max: number | null;
  contact_preferred_salary_min: number | null;
  contact_preferred_salary_max: number | null;
  experience_cards: ExperienceCard[];
  contact: ContactDetails | null;
};

export type DraftCard = {
  draft_card_id: string;
  title: string | null;
  context: string | null;
  constraints: string | null;
  decisions: string | null;
  outcome: string | null;
  tags: string[];
  company: string | null;
  team: string | null;
  role_title: string | null;
  time_range: string | null;
  source_span?: string | null;
};

export type DraftSet = {
  draft_set_id: string;
  raw_experience_id: string;
  cards: DraftCard[];
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
