"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
  password: z.string().min(1, "Password required"),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  return (
    <Suspense fallback={<LoadingScreen message="Loading..." />}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const { login, isAuthenticated, isAuthLoading, onboardingStep } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [verificationEmail, setVerificationEmail] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const redirectTo = getPostAuthPath(onboardingStep);

  useEffect(() => {
    if (!isAuthLoading && isAuthenticated) router.replace(redirectTo);
  }, [isAuthLoading, isAuthenticated, redirectTo, router]);

  useEffect(() => {
    const email = searchParams.get("email");
    if (email) setValue("email", email);
  }, [searchParams, setValue]);

  if (isAuthLoading || isAuthenticated) {
    return <LoadingScreen message="Loading..." />;
  }

  const onSubmit = async (data: FormData) => {
    setError(null);
    setVerificationEmail(null);
    try {
      await login(data.email, data.password);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Login failed";
      setError(message);
      if (message.toLowerCase().includes("email not verified")) {
        setVerificationEmail(data.email);
      }
    }
  };

  return (
    <AuthLayout
      title="CONXA"
      subtitle="Find people by what they've actually done. Trust-weighted, credit-governed search."
    >
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
      >
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Sign in</CardTitle>
            <CardDescription>
              Use your email and password to continue.
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
                  placeholder="Enter your password"
                  {...register("password")}
                />
                {errors.password && (
                  <p className="text-xs text-destructive">{errors.password.message}</p>
                )}
              </div>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>
              {verificationEmail && (
                <p className="text-center text-xs text-muted-foreground">
                  Your email is not verified.{" "}
                  <Link
                    href={`/verify-email?email=${encodeURIComponent(verificationEmail)}`}
                    className="text-foreground font-medium hover:underline"
                  >
                    Verify now
                  </Link>
                </p>
              )}
              <p className="text-center text-sm text-muted-foreground">
                {"Don't have an account? "}
                <Link href="/signup" className="text-foreground font-medium hover:underline">
                  Sign up
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </AuthLayout>
  );
}
