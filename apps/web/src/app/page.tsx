"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { LoadingScreen } from "@/components/feedback";

export default function RootPage() {
  const { token } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (token) router.replace("/home");
    else router.replace("/login");
  }, [token, router]);

  return <LoadingScreen />;
}
