"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Mic, MicOff, Loader2, PhoneOff, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import Vapi from "@vapi-ai/web";
import { API_BASE } from "@/lib/constants";
import { AUTH_TOKEN_KEY } from "@/lib/auth-flow";
import { EXPERIENCE_CARD_FAMILIES_QUERY_KEY } from "@/hooks";
import Link from "next/link";

export function VapiVoiceWidget() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const vapiRef = useRef<Vapi | null>(null);

  const getToken = () => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(AUTH_TOKEN_KEY);
  };

  const handleStart = useCallback(async () => {
    setError(null);
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

      vapi.on("error", (err) => {
        setError(err?.message ?? "Voice connection error");
      });

      await vapi.start({}); // Assistant config comes from our backend proxy
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not start voice session";
      setError(msg);
    } finally {
      setConnecting(false);
    }
  }, [queryClient]);

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
    <div className="flex flex-col items-center justify-center gap-4 p-6 rounded-lg border border-border bg-muted/30 min-h-[200px]">
      <p className="text-sm text-muted-foreground text-center max-w-sm">
        Use real-time voice to add an experience. Speak naturally—the AI will ask follow-up questions
        and build your card. Your cards will appear when you&apos;re done.
      </p>
      {error && (
        <p className="text-sm text-destructive text-center" role="alert">
          {error}
        </p>
      )}
      <div className="flex flex-col items-center gap-3">
        {!isConnected ? (
          <Button
            onClick={handleStart}
            disabled={connecting}
            size="lg"
            className="gap-2"
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
          </>
        )}
      </div>
      {isConnected && (
        <Link
          href="/cards"
          className="text-sm text-primary hover:underline"
        >
          View your cards →
        </Link>
      )}
    </div>
  );
}
