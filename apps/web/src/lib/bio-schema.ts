import { z } from "zod";

export const LINKEDIN_URL_REGEX = /^(https?:\/\/)?(www\.)?linkedin\.com\/in\/[\w-]+\/?$/i;
export const DOB_REGEX = /^\d{4}-\d{2}-\d{2}$/;

export const bioSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  date_of_birth: z.string().min(1, "Date of birth is required").refine(
    (val) => DOB_REGEX.test(val),
    "Use YYYY-MM-DD format"
  ),
  current_city: z.string().min(1, "Current city is required"),
  profile_photo_url: z.string().optional(),
  school: z.string().min(1, "School is required"),
  college: z.string().optional(),
  current_company: z.string().optional(),
  past_companies: z.array(
    z.object({
      company_name: z.string(),
      role: z.string().optional(),
      years: z.string().optional(),
    })
  ).optional(),
  email: z.string().email("Valid email is required"),
  linkedin_url: z
    .string()
    .optional()
    .refine((val) => !val || val.trim() === "" || LINKEDIN_URL_REGEX.test(val), {
      message: "Enter a valid LinkedIn profile URL (e.g. https://linkedin.com/in/username)",
    }),
  phone: z.string().optional(),
});

export type BioForm = z.infer<typeof bioSchema>;

export const bioFormDefaultValues: BioForm = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  current_city: "",
  profile_photo_url: "",
  school: "",
  college: "",
  current_company: "",
  past_companies: [],
  email: "",
  linkedin_url: "",
  phone: "",
};
