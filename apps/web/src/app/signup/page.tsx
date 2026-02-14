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

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(6, "At least 6 characters"),
  display_name: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

export default function SignupPage() {
  const { signup, isAuthenticated, isAuthLoading, onboardingStep } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const redirectTo = getPostAuthPath(onboardingStep);

  useEffect(() => {
    if (!isAuthLoading && isAuthenticated) router.replace(redirectTo);
  }, [isAuthLoading, isAuthenticated, redirectTo, router]);

  if (isAuthLoading || isAuthenticated) {
    return <LoadingScreen message="Loading..." />;
  }

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      await signup(data.email, data.password, data.display_name || undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign up failed");
    }
  };

  return (
    <AuthLayout
      title="CONXA"
      subtitle="Start with 1,000 credits. Build your experience and get discovered."
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
      >
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Sign up</CardTitle>
            <CardDescription>
              Email, password, and optional display name.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {error && <ErrorMessage message={error} />}
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
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
                  placeholder="At least 6 characters"
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
