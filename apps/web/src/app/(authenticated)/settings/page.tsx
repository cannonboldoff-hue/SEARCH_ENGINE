"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { LogOut, User, Coins, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { useCredits } from "@/hooks";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { data: credits } = useCredits();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your account and preferences.
        </p>
      </div>

      {/* Account */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <User className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Account</CardTitle>
              <CardDescription>
                Your sign-in identity.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground">Email</span>
              <span className="text-sm text-foreground font-medium">{user?.email ?? "--"}</span>
            </div>
            {user?.display_name && (
              <div className="flex flex-col">
                <span className="text-xs text-muted-foreground">Display name</span>
                <span className="text-sm text-foreground font-medium">{user.display_name}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Credits quick view */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <Coins className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Credits</CardTitle>
              <CardDescription>Your current balance and purchase options.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold tabular-nums text-foreground">
                {credits?.balance ?? "--"}
              </span>
              <span className="text-sm text-muted-foreground">credits remaining</span>
            </div>
            <Link href="/credits">
              <Button variant="outline" size="sm">
                Buy credits
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Sign out */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <Shield className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Session</CardTitle>
              <CardDescription>
                Sign out of this device. You can sign back in with the same email.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            size="sm"
            className="text-muted-foreground hover:text-destructive hover:border-destructive/50"
            onClick={() => logout()}
          >
            <LogOut className="h-3.5 w-3.5 mr-1.5" />
            Log out
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );
}
