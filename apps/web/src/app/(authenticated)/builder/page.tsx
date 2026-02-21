"use client";

import { useCallback } from "react";
import { motion } from "framer-motion";
import { BackLink } from "@/components/back-link";
import { BuilderChat } from "@/components/builder";
import { api } from "@/lib/api";
import type { TranslateTextResponse } from "@/types";

export default function BuilderPage() {
  const translateToEnglishForBackend = useCallback(async (text: string): Promise<string> => {
    const trimmed = text.trim();
    if (!trimmed) return "";
    try {
      const result = await api<TranslateTextResponse>("/experiences/translate", {
        method: "POST",
        body: { raw_text: trimmed },
      });
      const sourceLangRaw =
        typeof result?.source_language_code === "string" ? result.source_language_code.toLowerCase() : "";
      const isEnglish = sourceLangRaw.startsWith("en");
      if (!isEnglish && sourceLangRaw) return trimmed;
      const translated = typeof result?.translated_text === "string" ? result.translated_text.trim() : "";
      return translated || trimmed;
    } catch {
      return trimmed;
    }
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
        <div className="w-[4.5rem] sm:w-24 flex-shrink-0" aria-hidden />
      </div>
      <div className="flex-1 min-h-0 flex flex-col">
        <BuilderChat translateRawText={translateToEnglishForBackend} />
      </div>
    </motion.div>
  );
}
