"use client";

import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { BackLink } from "@/components/back-link";
import { BuilderChat, ElevenLabsVoiceWidget } from "@/components/builder";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function BuilderPage() {
  const [mode, setMode] = useState<"type" | "voice">("voice");

  const translateToEnglishForBackend = useCallback(async (text: string): Promise<string> => {
    return text.trim() || "";
  }, []);

  return (
    <motion.div
      className="flex flex-col min-h-0 h-[calc(100vh-5rem)] max-h-[calc(100vh-5rem)] overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-center justify-between gap-2 mb-2 sm:mb-3 flex-shrink-0 px-1">
        <BackLink href="/cards" className="min-w-0 flex-shrink-0" />
        <h1 className="text-base sm:text-lg font-semibold tracking-tight text-foreground truncate text-center flex-1 min-w-0">
          Add experience
        </h1>
        <div className="w-[4.5rem] sm:w-24 flex-shrink-0 flex justify-end">
          <div className="flex rounded-lg border border-border p-0.5">
            <Button
              variant="ghost"
              size="sm"
              className={cn("h-7 px-2 text-xs", mode === "voice" && "bg-muted")}
              onClick={() => setMode("voice")}
            >
              Voice
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className={cn("h-7 px-2 text-xs", mode === "type" && "bg-muted")}
              onClick={() => setMode("type")}
            >
              Type
            </Button>
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 flex flex-col">
        {mode === "voice" ? (
          <ElevenLabsVoiceWidget />
        ) : (
          <BuilderChat translateRawText={translateToEnglishForBackend} />
        )}
      </div>
    </motion.div>
  );
}
