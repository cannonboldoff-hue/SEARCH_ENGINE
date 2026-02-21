"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, Send, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { V1CardDetails } from "../card/v1-card-details";
import {
  STREAM_PROCESSOR_BUFFER,
  STREAM_SAMPLE_RATE,
  type StreamServerMessage,
  appendTranscriptText,
  arrayBufferToBase64,
  buildTranscribeWsUrl,
  downsampleTo16k,
  float32ToPcm16Buffer,
} from "@/lib/voice-transcribe";
import { AUTH_TOKEN_KEY } from "@/lib/auth-flow";
import {
  EXPERIENCE_CARDS_QUERY_KEY,
  EXPERIENCE_CARD_FAMILIES_QUERY_KEY,
} from "@/hooks";
import type {
  CardFamilyV1Response,
  DraftSetV1Response,
  DetectExperiencesResponse,
} from "@/types";

const PLACEHOLDER_FIRST_MESSAGE: ChatMessage = {
  id: "0",
  role: "assistant",
  content: "",
};

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  card?: CardFamilyV1Response;
};

type Stage =
  | "awaiting_experience"
  | "awaiting_choice"
  | "extracting"
  | "clarifying"
  | "card_ready"
  | "idle";

/** Structured clarify history entry for target-aware API. */
export type ClarifyHistoryEntry = {
  role: string;
  kind: "clarify_question" | "clarify_answer";
  target_type?: string | null;
  target_field?: string | null;
  target_child_type?: string | null;
  text: string;
};

/** One option for choose_focus (multiple experiences). */
export type ClarifyOption = { parent_id: string; label: string };

/** Clarify API response (target-aware). */
type ClarifyResponse = {
  clarifying_question?: string | null;
  filled?: Record<string, unknown>;
  should_stop?: boolean | null;
  stop_reason?: string | null;
  target_type?: string | null;
  target_field?: string | null;
  target_child_type?: string | null;
  progress?: { parent_asked?: number; child_asked?: number; max_parent?: number; max_child?: number } | null;
  asked_history_entry?: ClarifyHistoryEntry | null;
  canonical_family?: { parent?: Record<string, unknown>; children?: unknown[] } | null;
  /** choose_focus: multiple experiences, user must pick one first */
  action?: string | null;
  message?: string | null;
  options?: ClarifyOption[] | null;
  focus_parent_id?: string | null;
};

function buildSummaryFromParent(parent: Record<string, unknown>): string {
  const title = [parent.title, parent.normalized_role].find(Boolean) as string | undefined;
  const company = parent.company_name as string | undefined;
  const start = parent.start_date as string | undefined;
  const end = parent.end_date as string | undefined;
  const summary = parent.summary as string | undefined;
  const parts: string[] = [];
  if (title) parts.push(title);
  if (company) parts.push(`at ${company}`);
  if (start || end) parts.push([start, end].filter(Boolean).join(" – "));
  if (summary) parts.push(summary);
  return parts.join(". ") || "Your experience";
}

interface BuilderChatProps {
  translateRawText: (text: string) => Promise<string>;
  onCardsSaved?: () => void;
}

export function BuilderChat({ translateRawText, onCardsSaved }: BuilderChatProps) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([PLACEHOLDER_FIRST_MESSAGE]);
  const [loadingFirstMessage, setLoadingFirstMessage] = useState(true);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<Stage>("awaiting_experience");
  const [detectedExperiences, setDetectedExperiences] = useState<DetectExperiencesResponse | null>(null);
  const [currentExperienceText, setCurrentExperienceText] = useState("");
  const [currentCardFamily, setCurrentCardFamily] = useState<CardFamilyV1Response | null>(null);
  /** Structured clarify history for target-aware API (role, kind, target_type, target_field, target_child_type, text). */
  const [clarifyHistory, setClarifyHistory] = useState<ClarifyHistoryEntry[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnectingRecorder, setIsConnectingRecorder] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const lastTranscriptRef = useRef("");

  // Fetch LLM-generated opening question on mount (no hardcoded first message)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api<{ clarifying_question?: string | null }>(
          "/experience-cards/clarify-experience",
          {
            method: "POST",
            body: {
              raw_text: "",
              current_card: {},
              card_type: "parent",
              conversation_history: [],
            },
          }
        );
        const question = res?.clarifying_question?.trim();
        if (!cancelled && question) {
          setMessages((prev) =>
            prev.length > 0
              ? [{ ...prev[0], content: question }, ...prev.slice(1)]
              : [{ ...PLACEHOLDER_FIRST_MESSAGE, content: question }]
          );
        } else if (!cancelled) {
          setMessages((prev) =>
            prev.length > 0
              ? [{ ...prev[0], content: "What would you like to add? You can type or use the microphone." }, ...prev.slice(1)]
              : [{ ...PLACEHOLDER_FIRST_MESSAGE, content: "What would you like to add? You can type or use the microphone." }]
          );
        }
      } catch {
        if (!cancelled) {
          setMessages((prev) =>
            prev.length > 0
              ? [{ ...prev[0], content: "What would you like to add? You can type or use the microphone." }, ...prev.slice(1)]
              : [{ ...PLACEHOLDER_FIRST_MESSAGE, content: "What would you like to add? You can type or use the microphone." }]
          );
        }
      } finally {
        if (!cancelled) setLoadingFirstMessage(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMessage = useCallback((msg: Omit<ChatMessage, "id">) => {
    setMessages((prev) => [...prev, { ...msg, id: String(prev.length + Date.now()) }]);
  }, []);

  const cleanupAudio = useCallback(() => {
    processorNodeRef.current?.disconnect();
    processorNodeRef.current = null;
    sourceNodeRef.current?.disconnect();
    sourceNodeRef.current = null;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
  }, []);

  const stopRecording = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: "stop" }));
      } catch {}
      wsRef.current.close();
    }
    wsRef.current = null;
    cleanupAudio();
    setIsRecording(false);
    setIsConnectingRecorder(false);
    setLiveTranscript("");
    if (lastTranscriptRef.current.trim()) setInput((prev) => appendTranscriptText(prev, lastTranscriptRef.current));
    lastTranscriptRef.current = "";
  }, [cleanupAudio]);

  const startRecording = useCallback(async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem(AUTH_TOKEN_KEY) : null;
    if (!token) {
      setRecordingError("Please sign in to use voice.");
      return;
    }
    setRecordingError(null);
    setIsConnectingRecorder(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const sampleRate = 48000;
      const ctx = new AudioContext({ sampleRate });
      audioContextRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;
      const bufferSize = STREAM_PROCESSOR_BUFFER;
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1);
      processorNodeRef.current = processor;
      const wsUrl = buildTranscribeWsUrl(token);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as StreamServerMessage;
          if (data.type === "transcript" && data.transcript) {
            lastTranscriptRef.current = appendTranscriptText(lastTranscriptRef.current, data.transcript);
            setLiveTranscript(lastTranscriptRef.current);
          }
        } catch {}
      };
      ws.onopen = () => {
        setIsConnectingRecorder(false);
        setIsRecording(true);
      };
      ws.onerror = () => {
        setRecordingError("Connection failed");
        setIsConnectingRecorder(false);
      };
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);
        const downsampled = downsampleTo16k(float32, sampleRate);
        const pcm = float32ToPcm16Buffer(downsampled);
        ws.send(JSON.stringify({ type: "audio", audio: arrayBufferToBase64(pcm), encoding: "audio/pcm; rate=16000" }));
      };
      source.connect(processor);
      processor.connect(ctx.destination);
    } catch (e) {
      setRecordingError(e instanceof Error ? e.message : "Microphone access failed");
      setIsConnectingRecorder(false);
    }
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) stopRecording();
    else startRecording();
  }, [isRecording, startRecording, stopRecording]);

  const extractSingle = useCallback(
    async (
      experienceIndex: number,
      experienceCount: number,
      text: string
    ): Promise<{ summary: string; family: CardFamilyV1Response } | null> => {
      const english = await translateRawText(text);
      const res = await api<DraftSetV1Response>("/experience-cards/draft-v1-single", {
        method: "POST",
        body: {
          raw_text: english || text,
          experience_index: experienceIndex,
          experience_count: experienceCount,
        },
      });
      const families = res.card_families ?? [];
      if (families.length === 0) return null;
      const family = families[0];
      const parent = family.parent as Record<string, unknown>;
      const summary = buildSummaryFromParent(parent);
      setCurrentCardFamily(family);
      setClarifyHistory([]);
      return { summary, family };
    },
    [translateRawText]
  );

  const askClarify = useCallback(
    async (
      cardFamily: CardFamilyV1Response | null,
      history: ClarifyHistoryEntry[],
      opts?: { detectedExperiences?: { index: number; label: string }[]; rawTextOverride?: string }
    ): Promise<ClarifyResponse> => {
      const sourceText = opts?.rawTextOverride ?? currentExperienceText;
      const english = await translateRawText(sourceText);
      const parent = (cardFamily?.parent ?? {}) as Record<string, unknown>;
      const conversation_history = history.map((h) => ({ role: h.role, content: h.text }));
      let last_question_target: { target_type?: string; target_field?: string; target_child_type?: string } | undefined;
      if (history.length > 0 && history[history.length - 1].role === "user") {
        for (let i = history.length - 1; i >= 0; i--) {
          const e = history[i];
          if (e.role === "assistant" && e.kind === "clarify_question" && (e.target_type || e.target_field || e.target_child_type)) {
            last_question_target = {
              target_type: e.target_type ?? undefined,
              target_field: e.target_field ?? undefined,
              target_child_type: e.target_child_type ?? undefined,
            };
            break;
          }
        }
      }
      const body: Record<string, unknown> = {
        raw_text: english || sourceText,
        current_card: parent,
        card_type: "parent",
        conversation_history,
        card_family: cardFamily ? { parent: cardFamily.parent, children: cardFamily.children ?? [] } : undefined,
        asked_history: history.length ? history : undefined,
        last_question_target: last_question_target ?? undefined,
      };
      const parentId = cardFamily?.parent && typeof (cardFamily.parent as { id?: string }).id === "string"
        ? (cardFamily.parent as { id: string }).id
        : undefined;
      if (parentId) body.card_id = parentId;
      if (opts?.detectedExperiences?.length) {
        body.detected_experiences = opts.detectedExperiences.map((e) => ({ index: e.index, label: e.label }));
      }
      const res = await api<ClarifyResponse>("/experience-cards/clarify-experience", {
        method: "POST",
        body,
      });
      return res;
    },
    [currentExperienceText, translateRawText]
  );

  const mergeFilledIntoCard = useCallback(
    (filled: Record<string, unknown>) => {
      setCurrentCardFamily((prev) => {
        if (!prev) return prev;
        const parent = { ...(prev.parent as Record<string, unknown>), ...filled };
        return { ...prev, parent } as CardFamilyV1Response;
      });
    },
    []
  );

  const sendMessage = useCallback(async () => {
    const text = (input || liveTranscript || "").trim();
    if (!text || loading) return;
    setInput("");
    if (liveTranscript) {
      lastTranscriptRef.current = "";
      setLiveTranscript("");
    }
    if (isRecording) stopRecording();
    addMessage({ role: "user", content: text });

    if (stage === "awaiting_experience") {
      setCurrentExperienceText(text);
      setLoading(true);
      try {
        const english = await translateRawText(text);
        const detect = await api<DetectExperiencesResponse>("/experience-cards/detect-experiences", {
          method: "POST",
          body: { raw_text: english || text },
        });
        const count = detect.count ?? 0;
        const experiences = detect.experiences ?? [];
        if (count === 0 || experiences.length === 0) {
          addMessage({
            role: "assistant",
            content:
              "I didn't quite get that—what role or place were you at, and what did you do there?",
          });
          setStage("awaiting_experience");
          return;
        }
        if (count === 1) {
          const result = await extractSingle(1, 1, text);
          if (!result) {
            addMessage({
              role: "assistant",
              content: "Can you tell me a bit more—like where you worked and roughly when?",
            });
            setLoading(false);
            return;
          }
          const { summary, family } = result;
          addMessage({
            role: "assistant",
            content: `Here's what I understood: **${summary}**\n\nI have a few questions to get more detail.`,
          });
          const parent = family.parent as Record<string, unknown>;
          const firstClarify = await askClarify(family, [], { rawTextOverride: text });
          const firstEntry: ClarifyHistoryEntry | null = firstClarify.asked_history_entry ?? (firstClarify.clarifying_question ? {
            role: "assistant",
            kind: "clarify_question",
            target_type: firstClarify.target_type ?? null,
            target_field: firstClarify.target_field ?? null,
            target_child_type: firstClarify.target_child_type ?? null,
            text: firstClarify.clarifying_question,
          } : null);
          if (firstClarify.clarifying_question && firstEntry) {
            if (firstClarify.canonical_family?.parent) {
              setCurrentCardFamily((prev) =>
                prev
                  ? { ...prev, parent: firstClarify.canonical_family!.parent as CardFamilyV1Response["parent"], children: (firstClarify.canonical_family!.children as CardFamilyV1Response["children"]) ?? prev.children }
                  : prev
              );
            }
            setClarifyHistory([firstEntry]);
            addMessage({ role: "assistant", content: firstClarify.clarifying_question });
            setStage("clarifying");
          } else if (firstClarify.should_stop || (firstClarify.filled && Object.keys(firstClarify.filled).length > 0)) {
            if (firstClarify.filled && Object.keys(firstClarify.filled).length > 0) mergeFilledIntoCard(firstClarify.filled);
            queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
            const mergedParent = { ...parent, ...(firstClarify.filled || {}) } as CardFamilyV1Response["parent"];
            addMessage({
              role: "assistant",
              content: "Your experience card is ready. You can edit it anytime in **Your Cards**.",
              card: { ...family, parent: mergedParent },
            });
            setCurrentCardFamily(null);
            setStage("awaiting_experience");
            onCardsSaved?.();
          } else {
            addMessage({
              role: "assistant",
              content: "Your experience card is ready. You can edit it anytime in **Your Cards**.",
              card: family,
            });
            setCurrentCardFamily(null);
            setStage("awaiting_experience");
            queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
            onCardsSaved?.();
          }
          setLoading(false);
          return;
        }
        setDetectedExperiences({ count, experiences });
        const chooseRes = await askClarify(null, [], { detectedExperiences: experiences, rawTextOverride: text });
        if (chooseRes.action === "choose_focus" && chooseRes.message) {
          const list = (chooseRes.options ?? experiences.map((e) => ({ parent_id: String(e.index), label: e.label })))
            .map((o, i) => `**${i + 1}.** ${o.label}`)
            .join("\n");
          addMessage({
            role: "assistant",
            content: `${chooseRes.message}\n\n${list}\n\nReply with the number to pick one.`,
          });
        } else {
          const list = experiences
            .map((e) => `**${e.index}.** ${e.label}${e.suggested ? " (suggested)" : ""}`)
            .join("\n");
          addMessage({
            role: "assistant",
            content: `I found ${count} experiences. We'll build one card first—which one do you want to add? Reply with the number.\n\n${list}`,
          });
        }
        setStage("awaiting_choice");
      } catch (e) {
        addMessage({
          role: "assistant",
          content: "Something went wrong. Please try again or rephrase your experience.",
        });
        setStage("awaiting_experience");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (stage === "awaiting_choice") {
      const num = parseInt(text.replace(/\D/g, ""), 10);
      const exp = detectedExperiences?.experiences?.find((e) => e.index === num);
      if (!exp || !detectedExperiences) {
          addMessage({
            role: "assistant",
            content: "Which one do you want to add first? Just reply with the number.",
          });
        return;
      }
      setLoading(true);
      setDetectedExperiences(null);
      try {
        const result = await extractSingle(exp.index, detectedExperiences.count, currentExperienceText);
        if (!result) {
          addMessage({
            role: "assistant",
            content: "Can you tell me a bit more—like where you worked and roughly when?",
          });
          setStage("awaiting_experience");
          setLoading(false);
          return;
        }
        const { summary, family } = result;
        addMessage({
          role: "assistant",
          content: `Here's what I got: **${summary}**\n\nA couple of quick questions:`,
        });
        const parent = family.parent as Record<string, unknown>;
        const firstClarify = await askClarify(family, [], { rawTextOverride: currentExperienceText });
        const firstEntryChoice: ClarifyHistoryEntry | null = firstClarify.asked_history_entry ?? (firstClarify.clarifying_question ? {
          role: "assistant",
          kind: "clarify_question",
          target_type: firstClarify.target_type ?? null,
          target_field: firstClarify.target_field ?? null,
          target_child_type: firstClarify.target_child_type ?? null,
          text: firstClarify.clarifying_question,
        } : null);
        if (firstClarify.clarifying_question && firstEntryChoice) {
          if (firstClarify.canonical_family?.parent) {
            setCurrentCardFamily((prev) =>
              prev
                ? { ...prev, parent: firstClarify.canonical_family!.parent as CardFamilyV1Response["parent"], children: (firstClarify.canonical_family!.children as CardFamilyV1Response["children"]) ?? prev.children }
                : prev
            );
          }
          setClarifyHistory([firstEntryChoice]);
          addMessage({ role: "assistant", content: firstClarify.clarifying_question });
          setStage("clarifying");
        } else if (firstClarify.should_stop || (firstClarify.filled && Object.keys(firstClarify.filled).length > 0)) {
          if (firstClarify.filled && Object.keys(firstClarify.filled).length > 0) mergeFilledIntoCard(firstClarify.filled);
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
          const mergedParent = { ...parent, ...(firstClarify.filled || {}) } as CardFamilyV1Response["parent"];
          addMessage({
            role: "assistant",
            content: "Your experience card is ready. You can edit it anytime in **Your Cards**.",
            card: { ...family, parent: mergedParent },
          });
          setCurrentCardFamily(null);
          setStage("awaiting_experience");
          onCardsSaved?.();
        } else {
          addMessage({
            role: "assistant",
            content: "Your experience card is ready. You can edit it anytime in **Your Cards**.",
            card: family,
          });
          setCurrentCardFamily(null);
          setStage("awaiting_experience");
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
          onCardsSaved?.();
        }
      } catch (e) {
        addMessage({
          role: "assistant",
          content: "Something went wrong. Please try again.",
        });
        setStage("awaiting_experience");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (stage === "clarifying") {
      const userEntry: ClarifyHistoryEntry = { role: "user", kind: "clarify_answer", text };
      const history = [...clarifyHistory, userEntry];
      setClarifyHistory(history);
      setLoading(true);
      try {
        const res = await askClarify(currentCardFamily, history);
        const nextEntry: ClarifyHistoryEntry | null = res.asked_history_entry ?? (res.clarifying_question ? {
          role: "assistant",
          kind: "clarify_question",
          target_type: res.target_type ?? null,
          target_field: res.target_field ?? null,
          target_child_type: res.target_child_type ?? null,
          text: res.clarifying_question,
        } : null);
        if (res.clarifying_question && nextEntry) {
          // Update currentCardFamily with the canonical state returned by the backend
          if (res.canonical_family?.parent) {
            setCurrentCardFamily((prev) =>
              prev
                ? { ...prev, parent: res.canonical_family!.parent as CardFamilyV1Response["parent"], children: (res.canonical_family!.children as CardFamilyV1Response["children"]) ?? prev.children }
                : prev
            );
          }
          setClarifyHistory((h) => [...h, nextEntry]);
          addMessage({ role: "assistant", content: res.clarifying_question });
        } else if (res.should_stop || (res.filled && Object.keys(res.filled).length > 0)) {
          if (res.filled && Object.keys(res.filled).length > 0) mergeFilledIntoCard(res.filled);
          setClarifyHistory([]);
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
          const parent = (currentCardFamily?.parent ?? {}) as Record<string, unknown>;
          const mergedParent = { ...parent, ...(res.filled || {}) } as CardFamilyV1Response["parent"];
          const finalFamily: CardFamilyV1Response = currentCardFamily
            ? { ...currentCardFamily, parent: mergedParent }
            : { parent: mergedParent, children: [] };
          addMessage({
            role: "assistant",
            content: "Your experience card is ready. You can edit it anytime in **Your Cards**.",
            card: finalFamily,
          });
          setCurrentCardFamily(null);
          setStage("awaiting_experience");
          onCardsSaved?.();
        } else {
          addMessage({
            role: "assistant",
            content: "Your experience card is ready. You can edit it anytime in **Your Cards**.",
            card: currentCardFamily ?? undefined,
          });
          setCurrentCardFamily(null);
          setStage("awaiting_experience");
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
          onCardsSaved?.();
        }
      } catch (e) {
        addMessage({
          role: "assistant",
          content: "I had trouble with that. You can edit the card later in Your Cards.",
        });
        setStage("awaiting_experience");
      } finally {
        setLoading(false);
      }
    }
  }, [
    input,
    liveTranscript,
    loading,
    stage,
    currentExperienceText,
    currentCardFamily,
    detectedExperiences,
    clarifyHistory,
    addMessage,
    translateRawText,
    extractSingle,
    askClarify,
    mergeFilledIntoCard,
    queryClient,
    onCardsSaved,
    stopRecording,
  ]);

  return (
    <div className="flex flex-col h-full min-h-0 rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0" ref={scrollRef}>
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
                <p className="whitespace-pre-wrap break-words">
                  {msg.id === "0" && loadingFirstMessage ? (
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                      Thinking…
                    </span>
                  ) : (
                    msg.content.replace(/\*\*(.*?)\*\*/g, "$1")
                  )}
                </p>
                {msg.card && (
                  <>
                    <div className="mt-3 pt-3 border-t border-border/50">
                      <V1CardDetails
                        card={msg.card.parent as Record<string, unknown>}
                        compact
                        hideInternalFields
                      />
                    </div>
                    {(msg.card.children?.length ?? 0) > 0 && (
                      <div className="mt-2 pt-2 border-t border-border/40 space-y-1.5">
                        <p className="text-xs font-medium text-muted-foreground">
                          {msg.card.children!.length} thread{msg.card.children!.length !== 1 ? "s" : ""}
                        </p>
                        <ul className="space-y-1">
                          {msg.card.children!.map((child: Record<string, unknown>, i: number) => {
                            const value = child.value as Record<string, unknown> | undefined;
                            const headline =
                              (child.title as string) ??
                              (child.headline as string) ??
                              (value?.headline as string) ??
                              (value?.summary as string) ??
                              "Detail";
                            const summary =
                              (child.summary as string) ?? (value?.summary as string);
                            return (
                              <li
                                key={i}
                                className="text-xs rounded-md border border-border/40 bg-muted/30 px-2 py-1.5"
                              >
                                <span className="font-medium text-foreground">{headline}</span>
                                {summary && headline !== summary && (
                                  <p className="mt-0.5 text-muted-foreground line-clamp-2">
                                    {summary}
                                  </p>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}
                    <Link
                      href="/cards"
                      className="inline-block mt-2 text-xs font-medium text-primary hover:underline"
                    >
                      → Open Your Cards
                    </Link>
                  </>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-2.5 bg-muted/60 flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Thinking…</span>
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>
      {(isConnectingRecorder || isRecording || liveTranscript || recordingError) && (
        <div className="px-4 pb-2">
          <div className="rounded-lg border border-border/70 bg-muted/35 px-3 py-2 text-xs">
            {isConnectingRecorder && <p className="text-muted-foreground">Connecting…</p>}
            {isRecording && !isConnectingRecorder && (
              <p className="text-foreground">Listening…</p>
            )}
            {liveTranscript && <p className="text-muted-foreground truncate">Live: {liveTranscript}</p>}
            {recordingError && <p className="text-destructive">{recordingError}</p>}
          </div>
        </div>
      )}
      <div className="flex gap-2 p-3 border-t border-border flex-shrink-0">
        <textarea
          placeholder="Type or speak your experience…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          rows={2}
          className="flex-1 min-h-[44px] max-h-[120px] resize-none rounded-xl border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          disabled={loading}
        />
        <Button
          type="button"
          variant={isRecording ? "destructive" : "outline"}
          size="icon"
          onClick={toggleRecording}
          disabled={loading || isConnectingRecorder}
          className="shrink-0 h-11 w-11"
          aria-label={isRecording ? "Stop recording" : "Voice input"}
        >
          {isRecording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </Button>
        <Button
          type="button"
          size="icon"
          onClick={() => sendMessage()}
          disabled={(!input.trim() && !liveTranscript.trim()) || loading}
          className="shrink-0 h-11 w-11"
          aria-label="Send"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
