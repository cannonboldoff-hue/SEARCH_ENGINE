"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import { Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useCredits } from "@/hooks";

const PRICE_PER_CREDIT = 1; // ₹1 per credit

const PACKS = [
  { credits: 100, label: "100 credits" },
  { credits: 500, label: "500 credits" },
  { credits: 1000, label: "1,000 credits" },
  { credits: 5000, label: "5,000 credits" },
];

export default function CreditsPage() {
  const queryClient = useQueryClient();
  const { data: credits } = useCredits();

  const purchaseMutation = useMutation({
    mutationFn: (creditsAmount: number) =>
      api<{ balance: number }>("/me/credits/purchase", {
        method: "POST",
        body: { credits: creditsAmount },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credits"] });
    },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-xl mx-auto space-y-6"
    >
      <div>
        <Link
          href="/settings"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1 group mb-4"
        >
          <span className="transition-transform group-hover:-translate-x-0.5">{"<-"}</span> Back to settings
        </Link>
        <h1 className="text-lg font-semibold">Buy credits</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {"Use credits for search and unlocking contacts."}
        </p>
      </div>

      <Card>
        <CardHeader className="border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <Coins className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Current balance</CardTitle>
              <CardDescription>
                Your available credits.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular-nums text-foreground">
              {credits?.balance ?? "--"}
            </span>
            <span className="text-sm text-muted-foreground">credits</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b border-border pb-4">
          <CardTitle className="text-base">Choose a pack</CardTitle>
          <CardDescription>
            {"Select a pack and click Buy to add credits to your account."}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid gap-2 sm:grid-cols-2">
            {PACKS.map((pack) => {
              const priceRupees = pack.credits * PRICE_PER_CREDIT;
              const isPending =
                purchaseMutation.isPending &&
                purchaseMutation.variables === pack.credits;
              return (
                <div
                  key={pack.credits}
                  className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-accent transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{pack.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {"Rs."}{priceRupees.toLocaleString()}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => purchaseMutation.mutate(pack.credits)}
                    disabled={purchaseMutation.isPending}
                  >
                    {isPending ? "Adding..." : "Buy"}
                  </Button>
                </div>
              );
            })}
          </div>
          {purchaseMutation.isError && (
            <p className="text-xs text-destructive mt-3">
              {purchaseMutation.error instanceof Error
                ? purchaseMutation.error.message
                : "Failed to add credits."}
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
