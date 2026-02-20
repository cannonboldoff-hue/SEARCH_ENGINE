export type OnboardingStep = "bio" | "builder";
export const AUTH_TOKEN_KEY = "token";
export const ONBOARDING_STEP_KEY = "onboarding_step";
export const PENDING_ONBOARDING_STEP_KEY = "pending_onboarding_step";

export function getPostAuthPath(step: OnboardingStep | null): string {
  if (step === "bio") return "/onboarding/bio";
  if (step === "builder") return "/builder";
  return "/home";
}

export function isPathAllowedForStep(pathname: string, step: OnboardingStep | null): boolean {
  if (step == null) return true;
  return pathname === getPostAuthPath(step);
}

export function readPendingOnboardingStep(): OnboardingStep | null {
  if (typeof window === "undefined") return null;
  const step = localStorage.getItem(PENDING_ONBOARDING_STEP_KEY);
  return step === "bio" || step === "builder" ? step : null;
}

export function setPendingOnboardingStep(step: OnboardingStep | null): void {
  if (typeof window === "undefined") return;
  if (step) localStorage.setItem(PENDING_ONBOARDING_STEP_KEY, step);
  else localStorage.removeItem(PENDING_ONBOARDING_STEP_KEY);
}
