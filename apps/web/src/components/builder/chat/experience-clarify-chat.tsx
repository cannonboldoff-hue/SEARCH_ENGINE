"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MessageCircle, Send, Loader2 } from "lucide-react";

export type ClarifyMessage = { role: "assistant" | "user"; content: string };

export type ClarifyExperienceResponse = {
  clarifying_question?: string | null;
  filled?: Record<string, unknown>;
};

interface ExperienceClarifyChatProps {
  rawText: string;
  currentCard: Record<string, unknown>;
  cardType: "parent" | "child";
  cardId?: string | null;
  childId?: string | null;
  onFilled: (filled: Record<string, unknown>) => void;
  /** Optional: translate rawText before sending (e.g. to English). Receives raw text, returns translated. */
  translateRawText?: (text: string) => Promise<string>;
  className?: string;
}

export function ExperienceClarifyChat({
  rawText,
  currentCard,
  cardType,
  cardId,
  childId,
  onFilled,
  translateRawText,
  className,
}: ExperienceClarifyChatProps) {
  const [messages, setMessages] = useState<ClarifyMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendRequest = async (conversationHistory: ClarifyMessage[]) => {
    if (!rawText.trim()) {
      setError("Please add some experience text first.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const textToSend = translateRawText ? await translateRawText(rawText.trim()) : rawText.trim();
      const res = await api<ClarifyExperienceResponse>("/experience-cards/clarify-experience", {
        method: "POST",
        body: {
          raw_text: textToSend,
          current_card: currentCard,
          card_type: cardType,
          conversation_history: conversationHistory.map((m) => ({ role: m.role, content: m.content })),
          ...(cardId && cardType === "parent" ? { card_id: cardId } : {}),
          ...(childId && cardType === "child" ? { child_id: childId } : {}),
        },
      });
      if (res.filled && Object.keys(res.filled).length > 0) {
        onFilled(res.filled);
        setDone(true);
      } else if (res.clarifying_question) {
        setMessages((prev) => [...prev, { role: "assistant", content: res.clarifying_question! }]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    setStarted(true);
    await sendRequest([]);
  };

  const handleSend = async () => {
    const reply = input.trim();
    if (!reply || loading) return;
    const userMessage: ClarifyMessage = { role: "user", content: reply };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    await sendRequest([...messages, userMessage]);
  };

  if (done) {
    return (
      <div className={className}>
        <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
          I&apos;ve updated the card from your answers. You can edit any field above or ask again if something is missing.
        </div>
      </div>
    );
  }

  if (!started) {
    return (
      <div className={className}>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleStart}
          disabled={!rawText.trim() || loading}
          className="gap-2"
        >
          <MessageCircle className="h-3.5 w-3.5" />
          {loading ? "Asking…" : "Ask me questions to fill details"}
        </Button>
        {!rawText.trim() && (
          <p className="mt-1.5 text-xs text-muted-foreground">Add or paste experience text above first.</p>
        )}
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="rounded-lg border border-border bg-muted/20 overflow-hidden">
        <div className="max-h-[200px] overflow-y-auto p-3 space-y-3">
          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "text-sm rounded-md px-3 py-2 max-w-[90%]",
                m.role === "assistant"
                  ? "bg-primary/10 text-foreground mr-auto"
                  : "bg-muted ml-auto mr-0"
              )}
            >
              {m.content}
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Thinking…</span>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
        {error && <p className="px-3 pb-2 text-xs text-destructive">{error}</p>}
        <div className="flex gap-2 p-2 border-t border-border">
          <Textarea
            placeholder="Your answer…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={1}
            className="min-h-[36px] resize-none text-sm"
            disabled={loading}
          />
          <Button
            type="button"
            size="sm"
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="shrink-0"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
