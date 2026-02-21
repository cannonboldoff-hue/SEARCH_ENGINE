"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { getPostAuthPath } from "@/lib/auth-flow";
import { AuthLayout } from "@/components/auth";
import { LoadingScreen, ErrorMessage } from "@/components/feedback";

const signupSchema = z.object({
  email: z.string().email("Invalid email"),
  password: z
    .string()
    .min(8, "At least 8 characters")
    .regex(/[A-Za-z]/, "Include at least one letter")
    .regex(/\d/, "Include at least one number"),
  display_name: z.string().optional(),
});

type SignupFormData = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const { signup, isAuthenticated, isAuthLoading, onboardingStep } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormData>({ resolver: zodResolver(signupSchema) });

  const redirectTo = getPostAuthPath(onboardingStep);

  useEffect(() => {
    if (!isAuthLoading && isAuthenticated) router.replace(redirectTo);
  }, [isAuthLoading, isAuthenticated, redirectTo, router]);

  if (isAuthLoading || isAuthenticated) {
    return <LoadingScreen message="Loading..." />;
  }

  const onSubmitDetails = async (data: SignupFormData) => {
    setError(null);
    try {
      const result = await signup({
        email: data.email,
        password: data.password,
        displayName: data.display_name || undefined,
      });
      if (result.emailVerificationRequired) {
        router.replace(`/verify-email?email=${encodeURIComponent(data.email)}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign up failed");
    }
  };

  return (
    <AuthLayout
      title="CONXA"
      subtitle="Create your account. We'll send a verification email to activate it."
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
      >
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Sign up</CardTitle>
            <CardDescription>Enter your details. We'll email a verification link.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmitDetails)} className="space-y-4">
              {error && <ErrorMessage message={error} />}
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  autoCapitalize="none"
                  autoCorrect="off"
                  {...register("email")}
                />
                {errors.email && (
                  <p className="text-xs text-destructive">{errors.email.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  {...register("password")}
                />
                {errors.password && (
                  <p className="text-xs text-destructive">{errors.password.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="display_name">Display name (optional)</Label>
                <Input
                  id="display_name"
                  placeholder="How you want to be shown"
                  autoComplete="name"
                  {...register("display_name")}
                />
              </div>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Creating account..." : "Create account"}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link href="/login" className="text-foreground font-medium hover:underline">
                  Sign in
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </AuthLayout>
  );
}
