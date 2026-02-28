"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Loader2, PhoneOff, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import Vapi from "@vapi-ai/web";
import { API_BASE } from "@/lib/constants";
import { AUTH_TOKEN_KEY } from "@/lib/auth-flow";
import { EXPERIENCE_CARD_FAMILIES_QUERY_KEY } from "@/hooks";
import Link from "next/link";
import { cn } from "@/lib/utils";

type VoiceTranscriptMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

/** Vapi message event for transcript - can be lowercase or uppercase type */
function isTranscriptMessage(msg: unknown): msg is { type: string; role?: string; transcriptType?: string; transcript?: string } {
  if (!msg || typeof msg !== "object") return false;
  const m = msg as Record<string, unknown>;
  const type = String(m.type ?? "").toLowerCase();
  return type === "transcript" && typeof (m.transcript ?? m.content) === "string";
}

export function VapiVoiceWidget() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [messages, setMessages] = useState<VoiceTranscriptMessage[]>([]);
  const vapiRef = useRef<Vapi | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const getToken = () => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(AUTH_TOKEN_KEY);
  };

  const addTranscriptMessage = useCallback((role: "user" | "assistant", text: string) => {
    const t = (text ?? "").trim();
    if (!t) return;
    setMessages((prev) => [
      ...prev,
      { id: `${Date.now()}-${prev.length}`, role, content: t },
    ]);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleStart = useCallback(async () => {
    setError(null);
    setMessages([]);
    setConnecting(true);
    const token = getToken();
    if (!token) {
      setError("Please sign in to use voice");
      setConnecting(false);
      return;
    }
    if (!API_BASE || !API_BASE.startsWith("http")) {
      setError("API not configured");
      setConnecting(false);
      return;
    }
    const proxyBase = `${API_BASE}/convai`;
    try {
      const vapi = new Vapi(token, proxyBase);
      vapiRef.current = vapi;

      vapi.on("call-start", () => {
        setError(null);
        setIsConnected(true);
      });

      vapi.on("call-end", () => {
        setIsConnected(false);
        setIsSpeaking(false);
        vapiRef.current = null;
        queryClient.invalidateQueries({ queryKey: [EXPERIENCE_CARD_FAMILIES_QUERY_KEY] });
      });

      vapi.on("speech-start", () => setIsSpeaking(true));
      vapi.on("speech-end", () => setIsSpeaking(false));

      vapi.on("message", (msg: unknown) => {
        if (!isTranscriptMessage(msg)) return;
        const transcriptType = String((msg as Record<string, unknown>).transcriptType ?? "").toLowerCase();
        if (transcriptType && transcriptType !== "final") return;
        const text = (msg.transcript ?? (msg as Record<string, unknown>).content) as string;
        const role = (msg.role === "user" || msg.role === "assistant") ? msg.role : "assistant";
        addTranscriptMessage(role, text);
      });

      vapi.on("error", (err) => {
        const errObj = err as Record<string, unknown>;
        const errType = String(errObj?.type ?? "").toLowerCase();
        const errMsg = (err?.message as string) || "";
        // start-method-error = our proxy returned 503 (e.g. local/callback mismatch)
        const isLocal = typeof window !== "undefined" && /localhost|127\.0\.0\.1/.test(API_BASE);
        const friendlyMsg =
          errType === "start-method-error" && isLocal
            ? "Voice requires a tunnel for local development. Run ngrok http 8000 and set VAPI_CALLBACK_BASE_URL to the ngrok URL."
            : errMsg || "Voice connection error";
        setError(friendlyMsg);
      });

      await vapi.start({}); // Assistant config comes from our backend proxy
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not start voice session";
      setError(msg);
    } finally {
      setConnecting(false);
    }
  }, [queryClient, addTranscriptMessage]);

  const handleEnd = useCallback(async () => {
    try {
      if (vapiRef.current) {
        vapiRef.current.stop();
        vapiRef.current = null;
      }
    } catch {
      setError("Could not end session");
    }
  }, []);

  useEffect(() => {
    return () => {
      if (vapiRef.current) {
        vapiRef.current.stop();
        vapiRef.current = null;
      }
    };
  }, []);

  return (
    <div className="flex flex-col h-full min-h-0 rounded-xl border border-border bg-card overflow-hidden">
      {/* Transcript area - same layout as Type mode */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {!isConnected && messages.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Use real-time voice to add an experience. Speak naturally—the AI will ask follow-up questions
            and build your card. Your cards will appear when you&apos;re done.
          </p>
        )}
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted/60 text-foreground"
                )}
              >
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={scrollRef} />
      </div>

      {/* Footer - voice controls */}
      <div className="flex flex-col gap-2 p-3 border-t border-border flex-shrink-0">
        {error && (
          <p className="text-sm text-destructive text-center" role="alert">
            {error}
          </p>
        )}
        <div className="flex items-center justify-between gap-3">
          {!isConnected ? (
            <Button
              onClick={handleStart}
              disabled={connecting}
              size="lg"
              className="gap-2 flex-1"
            >
              {connecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Connecting…
                </>
              ) : (
                <>
                  <Mic className="h-4 w-4" />
                  Start voice
                </>
              )}
            </Button>
          ) : (
            <>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                {isSpeaking ? (
                  <Volume2 className="h-4 w-4 animate-pulse text-primary" />
                ) : (
                  <MicOff className="h-4 w-4" />
                )}
                <span>{isSpeaking ? "Listening…" : "Connected"}</span>
              </div>
              <Button
                variant="outline"
                onClick={handleEnd}
                size="lg"
                className="gap-2"
              >
                <PhoneOff className="h-4 w-4" />
                End session
              </Button>
              {isConnected && (
                <Link
                  href="/cards"
                  className="text-sm text-primary hover:underline shrink-0"
                >
                  View cards →
                </Link>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
