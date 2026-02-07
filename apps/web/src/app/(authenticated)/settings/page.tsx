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
      transition={{ duration: 0.35 }}
      className="max-w-xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your account.
        </p>
      </div>

      <Card>
        <CardHeader className="border-b border-border pb-4">
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
        <CardContent className="pt-4 space-y-2">
          <div className="text-sm">
            <span className="text-muted-foreground">Email:</span>{" "}
            <span className="text-foreground font-medium">{user?.email ?? "--"}</span>
          </div>
          {user?.display_name && (
            <div className="text-sm">
              <span className="text-muted-foreground">Display name:</span>{" "}
              <span className="text-foreground font-medium">{user.display_name}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-base">Sign out</CardTitle>
          <CardDescription>
            Sign out of this device. You can sign back in with the same email.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
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
