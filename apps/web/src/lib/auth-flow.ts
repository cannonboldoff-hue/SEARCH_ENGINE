export type OnboardingStep = "bio" | "builder";
export const AUTH_TOKEN_KEY = "token";
export const ONBOARDING_STEP_KEY = "onboarding_step";

export function getPostAuthPath(step: OnboardingStep | null): string {
  if (step === "bio") return "/onboarding/bio";
  if (step === "builder") return "/builder";
  return "/home";
}

export function isPathAllowedForStep(pathname: string, step: OnboardingStep | null): boolean {
  if (step == null) return true;
  return pathname === getPostAuthPath(step);
}
