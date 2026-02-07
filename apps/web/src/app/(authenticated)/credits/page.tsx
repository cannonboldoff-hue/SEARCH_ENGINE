"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Coins } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorMessage } from "@/components/error-message";
import { api } from "@/lib/api";
import { useCredits } from "@/hooks";
import { cn } from "@/lib/utils";

const PRICE_PER_CREDIT = 1; // Rs.1 per credit

const PACKS = [
  { credits: 100, label: "100 credits", popular: false },
  { credits: 500, label: "500 credits", popular: true },
  { credits: 1000, label: "1,000 credits", popular: false },
  { credits: 5000, label: "5,000 credits", popular: false },
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
          className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5 group mb-4"
        >
          <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
          Back to settings
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Buy credits</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {"Use credits for search and unlocking contacts."}
        </p>
      </div>

      {/* Current balance */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center">
              <Coins className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-base">Current balance</CardTitle>
              <CardDescription>Your available credits.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold tabular-nums text-foreground">
              {credits?.balance ?? "--"}
            </span>
            <span className="text-sm text-muted-foreground">credits</span>
          </div>
        </CardContent>
      </Card>

      {/* Packs */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Choose a pack</CardTitle>
          <CardDescription>
            {"Select a pack and click Buy to add credits to your account."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            {PACKS.map((pack) => {
              const priceRupees = pack.credits * PRICE_PER_CREDIT;
              const isPending =
                purchaseMutation.isPending &&
                purchaseMutation.variables === pack.credits;
              return (
                <div
                  key={pack.credits}
                  className={cn(
                    "relative flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-accent",
                    pack.popular
                      ? "border-primary/50 ring-1 ring-primary/20"
                      : "border-border"
                  )}
                >
                  {pack.popular && (
                    <span className="absolute -top-2.5 left-3 rounded-md bg-primary px-2 py-0.5 text-[10px] font-medium text-primary-foreground">
                      Popular
                    </span>
                  )}
                  <div>
                    <p className="text-sm font-medium text-foreground">{pack.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {"Rs. "}{priceRupees.toLocaleString()}
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
            <div className="mt-3">
              <ErrorMessage
                message={
                  purchaseMutation.error instanceof Error
                    ? purchaseMutation.error.message
                    : "Failed to add credits."
                }
              />
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
