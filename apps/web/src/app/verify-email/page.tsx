"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
import { AuthLayout } from "@/components/auth";
import { ErrorMessage } from "@/components/feedback";
import { api } from "@/lib/api";

const schema = z.object({
  email: z.string().email("Invalid email"),
  token: z.string().min(4, "Verification code required"),
});

type FormData = z.infer<typeof schema>;

export default function VerifyEmailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const autoAttempted = useRef(false);

  const {
    register,
    handleSubmit,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const verify = useCallback(async (email: string, token: string) => {
    setError(null);
    setSuccess(null);
    setIsVerifying(true);
    try {
      await api("/auth/verify-email", { method: "POST", body: { email, token } });
      router.replace(`/login?email=${encodeURIComponent(email)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setIsVerifying(false);
    }
  }, [router]);

  const onSubmit = async (data: FormData) => {
    await verify(data.email, data.token);
  };

  const onResend = async () => {
    const email = getValues("email")?.trim();
    if (!email) {
      setError("Enter your email to resend the verification email.");
      return;
    }
    setError(null);
    setSuccess(null);
    setIsResending(true);
    try {
      await api("/auth/verify-email/resend", { method: "POST", body: { email } });
      setSuccess("Verification email sent. Check your inbox and spam folder.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to resend verification email");
    } finally {
      setIsResending(false);
    }
  };

  useEffect(() => {
    const email = searchParams.get("email");
    const token = searchParams.get("token");
    if (email) setValue("email", email);
    if (token) setValue("token", token);
  }, [searchParams, setValue]);

  useEffect(() => {
    const email = searchParams.get("email");
    const token = searchParams.get("token");
    if (!email || !token || autoAttempted.current) return;
    autoAttempted.current = true;
    void verify(email, token);
  }, [searchParams, verify]);

  return (
    <AuthLayout
      title="Verify your email"
      subtitle="We sent a verification link and code. Enter it below to activate your account."
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.1 }}
      >
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Email verification</CardTitle>
            <CardDescription>
              Paste the code from the email or use the link you received.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {error && <ErrorMessage message={error} />}
              {success && (
                <div className="text-sm text-emerald-700 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2.5">
                  {success}
                </div>
              )}
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
                <Label htmlFor="token">Verification code</Label>
                <Input
                  id="token"
                  placeholder="Paste code from email"
                  {...register("token")}
                />
                {errors.token && (
                  <p className="text-xs text-destructive">{errors.token.message}</p>
                )}
              </div>
              <Button type="submit" className="w-full" disabled={isVerifying}>
                {isVerifying ? "Verifying..." : "Verify email"}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={onResend}
                disabled={isResending}
              >
                {isResending ? "Sending..." : "Resend verification email"}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                <Link
                  href={`/login?email=${encodeURIComponent(getValues("email") || "")}`}
                  className="text-foreground font-medium hover:underline"
                >
                  Back to sign in
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </AuthLayout>
  );
}
