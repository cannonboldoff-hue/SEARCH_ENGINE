"use client";

import { useState, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Mic, MicOff, Loader2, PhoneOff, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useConversation } from "@elevenlabs/react";
import { api } from "@/lib/api";
import { AUTH_TOKEN_KEY } from "@/lib/auth-flow";
import { EXPERIENCE_CARD_FAMILIES_QUERY_KEY } from "@/hooks";
import Link from "next/link";

type SignedUrlResponse = { signed_url: string; conversation_id?: string };

export function ElevenLabsVoiceWidget() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  const {
    startSession,
    endSession,
    status,
    isSpeaking,
  } = useConversation({
    onConnect: () => {
      setError(null);
    },
    onDisconnect: () => {
      // Refetch card families when voice session ends so new cards appear
      queryClient.invalidateQueries({ queryKey: [EXPERIENCE_CARD_FAMILIES_QUERY_KEY] });
    },
    onError: (err) => {
      setError(err ?? "Voice connection error");
    },
  });

  const handleStart = useCallback(async () => {
    setError(null);
    setConnecting(true);
    try {
      const res = await api<SignedUrlResponse>("/convai/signed-url", {
        method: "POST",
      });
      const signedUrl = res?.signed_url;
      if (!signedUrl) {
        throw new Error("No signed URL received");
      }
      await startSession({
        signedUrl,
        connectionType: "websocket",
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not start voice session";
      setError(msg);
    } finally {
      setConnecting(false);
    }
  }, [startSession]);

  const handleEnd = useCallback(async () => {
    try {
      await endSession();
    } catch {
      setError("Could not end session");
    }
  }, [endSession]);

  const isConnected = status === "connected";

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
      <div className="flex items-center gap-3">
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
