"use client";

import { motion } from "framer-motion";
import { LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";

export default function SettingsPage() {
  const { user, logout } = useAuth();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-2xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Account settings.
        </p>
      </div>

      <Card className="glass border-border/50 overflow-hidden">
        <CardHeader className="border-b border-border/50">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-muted flex items-center justify-center">
              <User className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-lg">Account</CardTitle>
              <CardDescription>
                Your sign-in identity.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-6 space-y-2">
          <p className="text-sm">
            <span className="text-muted-foreground">Email:</span>{" "}
            <span className="font-medium">{user?.email ?? "—"}</span>
          </p>
          {user?.display_name && (
            <p className="text-sm">
              <span className="text-muted-foreground">Display name:</span>{" "}
              <span className="font-medium">{user.display_name}</span>
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="glass border-border/50 overflow-hidden">
        <CardHeader className="border-b border-border/50">
          <CardTitle className="text-lg">Sign out</CardTitle>
          <CardDescription>
            Sign out of this device. You can sign back in with the same email.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <Button
            variant="outline"
            className="text-muted-foreground hover:text-destructive hover:border-destructive/50"
            onClick={() => logout()}
          >
            <LogOut className="h-4 w-4 mr-2" />
            Log out
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );
}
