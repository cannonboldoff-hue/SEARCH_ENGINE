"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, PenLine, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BackLink } from "@/components/back-link";
import { SaveCardsModal } from "@/components/builder/save-cards-modal";
import { DraftCardFamily } from "@/components/builder/draft-card-family";
import { SavedCardFamily } from "@/components/builder/saved-card-family";
import { useAuth } from "@/contexts/auth-context";
import { api } from "@/lib/api";
import { API_BASE } from "@/lib/constants";
import { AUTH_TOKEN_KEY } from "@/lib/auth-flow";
import {
  useExperienceCards,
  useExperienceCardFamilies,
  useCardMutations,
  useCardForms,
  EXPERIENCE_CARDS_QUERY_KEY,
  EXPERIENCE_CARD_FAMILIES_QUERY_KEY,
} from "@/hooks";
import type {
  CardFamilyV1Response,
  DraftSetV1Response,
  RewriteTextResponse,
  TranslateTextResponse,
  ExperienceCardV1,
  ExperienceCard,
  ExperienceCardChild,
} from "@/types";

/** Get stable id from draft parent (API may send id or card_id). */
function getDraftParentId(parent: unknown): string {
  if (!parent || typeof parent !== "object") return "";
  const p = parent as Record<string, unknown>;
  const raw = p.id ?? p.card_id;
  if (raw == null) return "";
  return String(raw).trim();
}

/** Get stable id from saved parent (ExperienceCard; may have id or card_id). */
function getSavedParentId(parent: unknown): string {
  return getDraftParentId(parent);
}

/** Ensure each draft family parent has an `id` for edit/delete (API may send id or card_id). */
function normalizeDraftFamilies(families: CardFamilyV1Response[]): CardFamilyV1Response[] {
  return families.map((fam) => {
    const parent = fam.parent as Record<string, unknown> | undefined;
    if (!parent) return fam;
    const id = getDraftParentId(parent);
    if (!id) return fam;
    return { ...fam, parent: { ...parent, id } as ExperienceCardV1 };
  });
}

const PARENT_FORM_STRING_KEYS = [
  "title", "summary", "normalized_role", "domain", "sub_domain", "company_name", "company_type",
  "location", "employment_type", "start_date", "end_date", "intent_primary", "intent_secondary_str",
  "seniority_level", "confidence_score",
] as const;

/** Merge parsed form into current: only set string fields that are currently empty (never overwrite checkboxes). */
function mergeParentForm(
  current: { [k: string]: string | boolean },
  parsed: { [k: string]: string | boolean }
): Partial<{ [k: string]: string | boolean }> {
  const updates: Partial<{ [k: string]: string | boolean }> = {};
  for (const key of PARENT_FORM_STRING_KEYS) {
    const cur = current[key];
    const val = parsed[key];
    const isEmpty = cur === undefined || cur === null || (typeof cur === "string" && String(cur).trim() === "");
    const hasValue = val !== undefined && val !== null && (typeof val !== "string" || String(val).trim() !== "");
    if (isEmpty && hasValue) updates[key] = val;
  }
  return updates;
}

function mergeChildForm(
  current: { [k: string]: string },
  parsed: { [k: string]: string }
): Partial<{ [k: string]: string }> {
  const updates: Partial<{ [k: string]: string }> = {};
  for (const key of Object.keys(parsed)) {
    const cur = current[key];
    const val = parsed[key];
    const isEmpty = cur == null || String(cur).trim() === "";
    const hasValue = val != null && String(val).trim() !== "";
    if (isEmpty && hasValue) updates[key] = val;
  }
  return updates;
}

const STREAM_SAMPLE_RATE = 16000;
const STREAM_PROCESSOR_BUFFER = 4096;

type StreamServerMessage =
  | { type: "transcript"; transcript?: string }
  | { type: "error"; detail?: string }
  | { type: "event"; event?: unknown };

function buildTranscribeWsUrl(token: string): string {
  const base = API_BASE.trim();
  if (!base.startsWith("http://") && !base.startsWith("https://")) {
    throw new Error("Voice input requires NEXT_PUBLIC_API_BASE_URL.");
  }
  const wsBase = base.replace(/^http/i, "ws").replace(/\/+$/, "");
  const params = new URLSearchParams({
    token,
    language_code: "unknown",
  });
  return `${wsBase}/experiences/transcribe/stream?${params.toString()}`;
}

function downsampleTo16k(input: Float32Array, inputSampleRate: number): Float32Array {
  if (inputSampleRate <= STREAM_SAMPLE_RATE) return input;
  const ratio = inputSampleRate / STREAM_SAMPLE_RATE;
  const outputLength = Math.round(input.length / ratio);
  const output = new Float32Array(outputLength);
  let outputOffset = 0;
  let inputOffset = 0;

  while (outputOffset < outputLength) {
    const nextInputOffset = Math.round((outputOffset + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = inputOffset; i < nextInputOffset && i < input.length; i += 1) {
      accum += input[i];
      count += 1;
    }
    output[outputOffset] = count > 0 ? accum / count : 0;
    outputOffset += 1;
    inputOffset = nextInputOffset;
  }
  return output;
}

function float32ToPcm16Buffer(floatBuffer: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(floatBuffer.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < floatBuffer.length; i += 1) {
    const s = Math.max(-1, Math.min(1, floatBuffer[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...Array.from(chunk));
  }
  return btoa(binary);
}

function appendTranscriptText(current: string, nextText: string): string {
  const clean = nextText.trim();
  if (!clean) return current;
  if (!current.trim()) return clean;
  return `${current}${/\s$/.test(current) ? "" : " "}${clean}`;
}

export default function BuilderPage() {
  const router = useRouter();
  const { setOnboardingStep } = useAuth();
  const queryClient = useQueryClient();
  const [rawText, setRawText] = useState("");
  const [draftSetId, setDraftSetId] = useState<string | null>(null);
  const [cardFamilies, setCardFamilies] = useState<CardFamilyV1Response[] | null>(null);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [deletedId, setDeletedId] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isRewriting, setIsRewriting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [editingKind, setEditingKind] = useState<"parent" | "child" | null>(null);
  const [editingSavedCardId, setEditingSavedCardId] = useState<string | null>(null);
  const [editingSavedChildId, setEditingSavedChildId] = useState<string | null>(null);
  const [isUpdatingFromMessyText, setIsUpdatingFromMessyText] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnectingRecorder, setIsConnectingRecorder] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [recordingError, setRecordingError] = useState<string | null>(null);

  const recorderSocketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const lastServerTranscriptRef = useRef("");

  const { data: savedCards = [], isLoading: loadingCards } = useExperienceCards();
  const { data: savedFamilies = [], isLoading: loadingFamilies } = useExperienceCardFamilies();

  const {
    editForm,
    setEditForm,
    childEditForm,
    setChildEditForm,
    populateParentForm,
    populateChildForm,
  } = useCardForms();

  const {
    deleteCardMutation,
    patchCardMutation,
    patchChildMutation,
    deleteChildMutation,
  } = useCardMutations(
    setCardFamilies,
    setEditingCardId,
    setEditingKind,
    setEditingSavedCardId,
    setEditingSavedChildId
  );

  const cleanupAudioGraph = useCallback(() => {
    if (processorNodeRef.current) {
      processorNodeRef.current.onaudioprocess = null;
      processorNodeRef.current.disconnect();
      processorNodeRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (audioContextRef.current) {
      const ctx = audioContextRef.current;
      audioContextRef.current = null;
      void ctx.close().catch(() => undefined);
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  }, []);

  const stopRecording = useCallback((sendStopSignal = true) => {
    const ws = recorderSocketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && sendStopSignal) {
      try {
        ws.send(JSON.stringify({ type: "stop" }));
      } catch {
        // Ignore close race.
      }
    }
    if (ws && ws.readyState < WebSocket.CLOSING) {
      ws.close();
    }
    recorderSocketRef.current = null;
    cleanupAudioGraph();
    setIsRecording(false);
    setIsConnectingRecorder(false);
    setLiveTranscript("");
    lastServerTranscriptRef.current = "";
  }, [cleanupAudioGraph]);

  useEffect(() => {
    return () => {
      stopRecording(false);
    };
  }, [stopRecording]);

  const startRecording = useCallback(async () => {
    if (isRecording || isConnectingRecorder) return;
    if (typeof window === "undefined") return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setRecordingError("Microphone access is not supported in this browser.");
      return;
    }

    setRecordingError(null);
    setIsConnectingRecorder(true);
    setLiveTranscript("");
    lastServerTranscriptRef.current = "";

    try {
      const token = localStorage.getItem(AUTH_TOKEN_KEY);
      if (!token) throw new Error("Please log in again to use voice input.");

      const wsUrl = buildTranscribeWsUrl(token);
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          noiseSuppression: true,
          echoCancellation: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      const processor = audioContext.createScriptProcessor(STREAM_PROCESSOR_BUFFER, 1, 1);
      processorNodeRef.current = processor;
      source.connect(processor);
      processor.connect(audioContext.destination);

      const ws = new WebSocket(wsUrl);
      recorderSocketRef.current = ws;

      ws.onopen = () => {
        setIsConnectingRecorder(false);
        setIsRecording(true);
        setRecordingError(null);
      };

      ws.onmessage = (event) => {
        let msg: StreamServerMessage | null = null;
        try {
          msg = JSON.parse(event.data) as StreamServerMessage;
        } catch {
          return;
        }
        if (!msg || typeof msg !== "object") return;

        if (msg.type === "transcript") {
          const transcript = typeof msg.transcript === "string" ? msg.transcript.trim() : "";
          if (!transcript) return;
          setLiveTranscript(transcript);

          const previous = lastServerTranscriptRef.current;
          let delta = transcript;
          if (previous && transcript.startsWith(previous)) {
            delta = transcript.slice(previous.length);
          } else if (previous && previous.startsWith(transcript)) {
            delta = "";
          }

          if (delta.trim()) {
            setRawText((current) => appendTranscriptText(current, delta));
          }
          lastServerTranscriptRef.current = transcript;
          return;
        }

        if (msg.type === "error") {
          setRecordingError(msg.detail || "Voice transcription failed.");
          return;
        }
      };

      ws.onerror = () => {
        setRecordingError("Voice transcription connection failed.");
      };

      ws.onclose = () => {
        recorderSocketRef.current = null;
        cleanupAudioGraph();
        setIsRecording(false);
        setIsConnectingRecorder(false);
      };

      processor.onaudioprocess = (audioEvent) => {
        const socket = recorderSocketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        const floatData = audioEvent.inputBuffer.getChannelData(0);
        const downsampled = downsampleTo16k(floatData, audioContext.sampleRate);
        if (downsampled.length === 0) return;
        const pcmBuffer = float32ToPcm16Buffer(downsampled);
        const b64 = arrayBufferToBase64(pcmBuffer);
        socket.send(
          JSON.stringify({
            type: "audio_chunk",
            data: b64,
            sample_rate: STREAM_SAMPLE_RATE,
          })
        );
      };
    } catch (e) {
      cleanupAudioGraph();
      const ws = recorderSocketRef.current;
      if (ws && ws.readyState < WebSocket.CLOSING) ws.close();
      recorderSocketRef.current = null;
      setIsConnectingRecorder(false);
      setIsRecording(false);
      setRecordingError(e instanceof Error ? e.message : "Unable to start voice input.");
    }
  }, [cleanupAudioGraph, isConnectingRecorder, isRecording]);

  const toggleRecording = useCallback(() => {
    if (isRecording || isConnectingRecorder) {
      stopRecording(true);
      return;
    }
    void startRecording();
  }, [isConnectingRecorder, isRecording, startRecording, stopRecording]);

  const rewriteText = useCallback(async () => {
    if (isRecording || isConnectingRecorder) {
      stopRecording(true);
    }
    if (!rawText.trim()) return;
    setIsRewriting(true);
    try {
      const result = await api<RewriteTextResponse>("/experiences/rewrite", {
        method: "POST",
        body: { raw_text: rawText },
      });
      if (result?.rewritten_text != null) setRawText(result.rewritten_text);
    } catch (e) {
      console.error("Rewrite failed", e);
    } finally {
      setIsRewriting(false);
    }
  }, [isConnectingRecorder, isRecording, rawText, stopRecording]);

  const translateToEnglishForBackend = useCallback(async (text: string): Promise<string> => {
    const trimmed = text.trim();
    if (!trimmed) return "";
    try {
      const result = await api<TranslateTextResponse>("/experiences/translate", {
        method: "POST",
        body: { raw_text: trimmed },
      });
      const translated = typeof result?.translated_text === "string" ? result.translated_text.trim() : "";
      return translated || trimmed;
    } catch (e) {
      console.error("Backend pre-translation failed, using original text", e);
      return trimmed;
    }
  }, []);

  const extractDraftV1 = useCallback(async () => {
    if (isRecording || isConnectingRecorder) {
      stopRecording(true);
    }
    if (!rawText.trim()) {
      setDraftSetId(null);
      setCardFamilies([]);
      return;
    }
    setIsUpdating(true);
    try {
      const englishText = await translateToEnglishForBackend(rawText);
      const result = await api<DraftSetV1Response>("/experience-cards/draft-v1", {
        method: "POST",
        body: { raw_text: englishText || rawText },
      });
      setDraftSetId(result.draft_set_id ?? null);
      setCardFamilies(normalizeDraftFamilies(result.card_families ?? []));
    } catch (e) {
      console.error("Draft V1 failed", e);
    } finally {
      setIsUpdating(false);
    }
  }, [isConnectingRecorder, isRecording, rawText, stopRecording, translateToEnglishForBackend]);

  const startEditingCard = useCallback(
    (card: ExperienceCardV1 | Record<string, unknown>) => {
      const id = getDraftParentId(card);
      if (!id) return;
      setEditingCardId(id);
      setEditingKind("parent");
      setEditingSavedCardId(null);
      populateParentForm(card as ExperienceCardV1);
    },
    [populateParentForm]
  );

  const startEditingSavedCard = useCallback(
    (card: ExperienceCard | Record<string, unknown>) => {
      const id = getSavedParentId(card);
      if (!id) return;
      setEditingSavedCardId(id);
      setEditingCardId(null);
      setEditingKind(null);
      populateParentForm(card as ExperienceCard);
    },
    [populateParentForm]
  );

  const startEditingChild = useCallback(
    (child: ExperienceCardChild | (Record<string, unknown> & { id?: string })) => {
      const id = (child as { id?: string }).id ?? "";
      if (!id) return;
      setEditingSavedChildId(null);
      setEditingCardId(id);
      setEditingKind("child");
      populateChildForm(child);
    },
    [populateChildForm]
  );

  const startEditingSavedChild = useCallback(
    (child: ExperienceCardChild) => {
      setEditingCardId(null);
      setEditingKind(null);
      setEditingSavedChildId(child.id);
      populateChildForm(child);
    },
    [populateChildForm]
  );

  const submitEditCard = useCallback(() => {
    const cardId = editingSavedCardId ?? (editingKind === "parent" ? editingCardId : null);
    if (!cardId) return;
    const toNull = (s: string) => (s.trim() ? s.trim() : null);
    const intentSecondary = editForm.intent_secondary_str
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const confNum = editForm.confidence_score.trim() ? Number(editForm.confidence_score) : null;
    patchCardMutation.mutate({
      cardId,
      body: {
        title: toNull(editForm.title),
        summary: toNull(editForm.summary),
        normalized_role: toNull(editForm.normalized_role),
        domain: toNull(editForm.domain),
        sub_domain: toNull(editForm.sub_domain),
        company_name: toNull(editForm.company_name),
        company_type: toNull(editForm.company_type),
        location: toNull(editForm.location),
        employment_type: toNull(editForm.employment_type),
        start_date: toNull(editForm.start_date),
        end_date: toNull(editForm.end_date),
        is_current: editForm.is_current,
        intent_primary: toNull(editForm.intent_primary),
        intent_secondary: intentSecondary.length ? intentSecondary : null,
        seniority_level: toNull(editForm.seniority_level),
        confidence_score: confNum != null && !Number.isNaN(confNum) ? confNum : null,
        experience_card_visibility: editForm.experience_card_visibility,
      },
    });
  }, [editingCardId, editingKind, editingSavedCardId, editForm, patchCardMutation]);

  const submitEditChild = useCallback(() => {
    const childId = editingSavedChildId ?? (editingKind === "child" ? editingCardId : null);
    if (!childId) return;
    const tags = childEditForm.tagsStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    patchChildMutation.mutate({
      childId,
      body: {
        title: childEditForm.title.trim(),
        summary: childEditForm.summary.trim(),
        tags,
        time_range: childEditForm.time_range.trim(),
        company: childEditForm.company.trim(),
        location: childEditForm.location.trim(),
      },
    });
  }, [childEditForm, editingCardId, editingKind, editingSavedChildId, patchChildMutation]);

  const handleDeleteParentCard = useCallback(
    (cardId: string) => {
      setEditingCardId(null);
      setEditingKind(null);
      deleteCardMutation.mutate(cardId);
    },
    [deleteCardMutation]
  );

  const handleDeleteChildCard = useCallback(
    (childId: string) => {
      setEditingCardId(null);
      setEditingKind(null);
      deleteChildMutation.mutate(childId);
    },
    [deleteChildMutation]
  );

  const handleUpdateParentFromMessyText = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      setIsUpdatingFromMessyText(true);
      try {
        const englishText = await translateToEnglishForBackend(text);
        const cardId = editingSavedCardId ?? (editingKind === "parent" ? editingCardId : null);
        const result = await api<{ filled: Record<string, unknown> }>(
          "/experience-cards/fill-missing-from-text",
          {
            method: "POST",
            body: {
              raw_text: englishText,
              card_type: "parent",
              current_card: editForm,
              ...(cardId ? { card_id: cardId } : {}),
            },
          }
        );
        const filled = result?.filled ?? {};
        if (Object.keys(filled).length > 0) {
          setEditForm((prev) => {
            const updates = mergeParentForm(
              prev as unknown as { [k: string]: string | boolean },
              filled as { [k: string]: string | boolean }
            );
            return Object.keys(updates).length ? { ...prev, ...updates } : prev;
          });
        }
        if (cardId) {
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
        }
      } catch (e) {
        console.error("Update from messy text failed", e);
      } finally {
        setIsUpdatingFromMessyText(false);
      }
    },
    [editForm, setEditForm, editingCardId, editingKind, editingSavedCardId, queryClient, translateToEnglishForBackend]
  );

  const handleUpdateChildFromMessyText = useCallback(
    async (text: string) => {
      if (!text.trim()) return;
      setIsUpdatingFromMessyText(true);
      try {
        const englishText = await translateToEnglishForBackend(text);
        const childId = editingSavedChildId ?? (editingKind === "child" ? editingCardId : null);
        const result = await api<{ filled: Record<string, unknown> }>(
          "/experience-cards/fill-missing-from-text",
          {
            method: "POST",
            body: {
              raw_text: englishText,
              card_type: "child",
              current_card: childEditForm,
              ...(childId ? { child_id: childId } : {}),
            },
          }
        );
        const filled = result?.filled ?? {};
        if (Object.keys(filled).length > 0) {
          setChildEditForm((prev) => {
            const updates = mergeChildForm(
              prev as unknown as { [k: string]: string },
              filled as { [k: string]: string }
            );
            return Object.keys(updates).length ? { ...prev, ...updates } : prev;
          });
        }
        if (childId) {
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
        }
      } catch (e) {
        console.error("Update from messy text failed", e);
      } finally {
        setIsUpdatingFromMessyText(false);
      }
    },
    [childEditForm, setChildEditForm, editingCardId, editingKind, editingSavedChildId, queryClient, translateToEnglishForBackend]
  );

  const handleSaveCards = useCallback(async () => {
    setSaveError(null);
    setIsSavingAll(true);
    try {
      setSaveModalOpen(false);
      setDraftSetId(null);
      setCardFamilies(null);
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
      setOnboardingStep(null);
      router.push("/home");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save cards");
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARDS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: EXPERIENCE_CARD_FAMILIES_QUERY_KEY });
    } finally {
      setIsSavingAll(false);
    }
  }, [draftSetId, queryClient, router, setOnboardingStep]);

  const hasV1Families = (cardFamilies?.length ?? 0) > 0;
  const hasCards = hasV1Families || (draftSetId == null && savedFamilies.length > 0);

  return (
    <motion.div
      className="flex flex-col min-h-0 lg:h-[calc(100vh-7rem)] lg:max-h-[calc(100vh-6.5rem)] lg:overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-center justify-between gap-2 mb-3 sm:mb-4 flex-shrink-0 px-1">
        <BackLink href="/profile" className="min-w-0 flex-shrink-0" />
        <h1 className="text-base sm:text-lg font-semibold tracking-tight text-foreground truncate text-center flex-1 min-w-0">
          Experience Builder
        </h1>
        <div className="w-[4.5rem] sm:w-24 flex-shrink-0" aria-hidden />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 flex-1 min-h-0 overflow-hidden">
        {/* Left: Raw input */}
        <div className="flex flex-col min-h-[280px] lg:min-h-0 border border-border rounded-xl p-3 sm:p-4 bg-card overflow-hidden">
          <h2 className="text-sm sm:text-base font-medium text-foreground mb-1 flex-shrink-0">Your experience</h2>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-2 sm:mb-3 flex-shrink-0">
            <p className="text-xs text-muted-foreground text-left sm:pr-4">
              {"Write freely in any language. We auto-translate to English before backend processing and structure it into cards."}
            </p>
            <div className="flex items-center justify-end gap-2 flex-wrap sm:flex-nowrap">
              <Button
                variant={isRecording ? "destructive" : "outline"}
                size="sm"
                onClick={toggleRecording}
                disabled={isConnectingRecorder}
                className="flex-shrink-0 min-h-[2.75rem] touch-manipulation"
              >
                {isRecording ? <Square className="h-3.5 w-3.5 mr-1.5" /> : <Mic className="h-3.5 w-3.5 mr-1.5" />}
                {isConnectingRecorder ? "Connecting..." : isRecording ? "Stop Voice" : "Voice"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={rewriteText}
                disabled={!rawText.trim() || isRewriting}
                className="flex-shrink-0 min-h-[2.75rem] touch-manipulation"
              >
                <PenLine className="h-3.5 w-3.5 mr-1.5" />
                {isRewriting ? "Rewriting..." : "Rewrite"}
              </Button>
            </div>
          </div>
          {(isConnectingRecorder || isRecording || liveTranscript || recordingError) && (
            <div className="mb-2 sm:mb-3 flex-shrink-0 rounded-md border border-border/70 bg-muted/35 p-2">
              {isConnectingRecorder && (
                <p className="text-xs text-muted-foreground">Connecting microphone and live transcription...</p>
              )}
              {isRecording && !isConnectingRecorder && (
                <p className="text-xs text-foreground">Listening. Speak naturally and your words will be added below.</p>
              )}
              {liveTranscript && (
                <p className="text-xs text-muted-foreground mt-1 truncate">Live: {liveTranscript}</p>
              )}
              {recordingError && (
                <p className="text-xs text-destructive mt-1">{recordingError}</p>
              )}
            </div>
          )}
          <Textarea
            placeholder="Paste or type your experience. e.g. I worked at Razorpay in the backend team for 2 years..."
            className="min-h-[140px] sm:min-h-[200px] lg:min-h-[240px] resize-y flex-1 font-mono text-sm touch-manipulation"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
          />
          <div className="mt-2 sm:mt-3 space-y-1 flex-shrink-0">
            <Button
              onClick={extractDraftV1}
              disabled={!rawText.trim() || isUpdating}
              className="w-full sm:w-auto min-h-[2.75rem] touch-manipulation"
            >
              {isUpdating ? "Structuring..." : "Update"}
            </Button>
          </div>
        </div>

        {/* Right: Experience cards */}
        <div className="flex flex-col min-h-[260px] lg:min-h-0 border border-border rounded-xl p-3 sm:p-4 bg-card flex-1 overflow-hidden">
          <h2 className="text-sm sm:text-base font-medium text-foreground mb-2 sm:mb-3 flex-shrink-0">Experience cards</h2>
          {(deleteCardMutation.isError || deleteChildMutation.isError) && (
            <p className="text-sm text-destructive mb-2">
              {deleteCardMutation.error?.message ?? deleteChildMutation.error?.message ?? "Delete failed"}
            </p>
          )}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
            {(loadingCards || loadingFamilies) && savedFamilies.length === 0 && !hasV1Families ? (
              <motion.div
                className="flex flex-col items-center justify-center py-12 text-muted-foreground"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                <motion.div
                  className="h-12 w-12 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center mb-2"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                />
                <p className="text-sm">Loading…</p>
              </motion.div>
            ) : !hasCards ? (
              <motion.div
                className="flex flex-col items-center justify-center py-12 text-muted-foreground text-center"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.35 }}
              >
                <motion.div
                  className="h-12 w-12 rounded-full border border-dashed border-muted-foreground/50 flex items-center justify-center mb-3"
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                {draftSetId != null ? (
                  <>
                    <p className="font-medium text-foreground">No experiences extracted</p>
                    <p className="text-sm mt-1">We couldn’t structure this into cards. Try adding more detail (e.g. role, company, duration) and click Update again.</p>
                  </>
                ) : (
                  <>
                    <p className="font-medium text-foreground">No cards yet</p>
                    <p className="text-sm mt-1">Write something on the left and click Update.</p>
                  </>
                )}
              </motion.div>
            ) : (
              <>
                {isUpdating && (
                  <motion.div
                    className="space-y-2"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    {[1, 2, 3].map((i) => (
                      <motion.div
                        key={i}
                        className="h-32 rounded-xl bg-muted/50 border border-border/50"
                        initial={{ opacity: 0.4, x: -8 }}
                        animate={{ opacity: 0.7, x: 0 }}
                        transition={{ delay: i * 0.1, duration: 0.4, repeat: Infinity, repeatType: "reverse", repeatDelay: 0.2 }}
                      />
                    ))}
                  </motion.div>
                )}
                <AnimatePresence mode="popLayout">
                  {cardFamilies?.map((family, i) => (
                    <DraftCardFamily
                      key={getDraftParentId(family.parent) || `draft-family-${i}`}
                      family={family}
                      editingCardId={editingCardId}
                      editingKind={editingKind}
                      editForm={editForm}
                      childEditForm={childEditForm}
                      onEditFormChange={(updates) => setEditForm((f) => ({ ...f, ...updates }))}
                      onChildEditFormChange={(updates) => setChildEditForm((f) => ({ ...f, ...updates }))}
                      onStartEditingCard={startEditingCard}
                      onStartEditingChild={startEditingChild}
                      onSubmitEditCard={submitEditCard}
                      onSubmitEditChild={submitEditChild}
                      onDeleteParentCard={handleDeleteParentCard}
                      onDeleteChildCard={handleDeleteChildCard}
                      onUpdateParentFromMessyText={handleUpdateParentFromMessyText}
                      onUpdateChildFromMessyText={handleUpdateChildFromMessyText}
                      isUpdatingFromMessyText={isUpdatingFromMessyText}
                      isCardSubmitting={patchCardMutation.isPending}
                      isCardDeleting={deleteCardMutation.isPending}
                      isChildSubmitting={patchChildMutation.isPending}
                      isChildDeleting={deleteChildMutation.isPending}
                    />
                  ))}
                </AnimatePresence>
                {draftSetId == null && savedFamilies.length > 0 && (
                  <motion.div
                    className="mt-4 pt-4 border-t border-border/50 space-y-3"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    <p className="text-xs font-medium text-muted-foreground mb-2">Saved cards</p>
                    {savedFamilies.map((family, i) => (
                      <SavedCardFamily
                        key={getSavedParentId(family.parent) || `saved-family-${i}`}
                        parent={family.parent}
                        children={family.children}
                        deletedId={deletedId}
                        editingSavedCardId={editingSavedCardId}
                        editingSavedChildId={editingSavedChildId}
                        editForm={editForm}
                        childEditForm={childEditForm}
                        onEditFormChange={(updates) => setEditForm((f) => ({ ...f, ...updates }))}
                        onChildEditFormChange={(updates) => setChildEditForm((f) => ({ ...f, ...updates }))}
                        onStartEditing={startEditingSavedCard}
                        onStartEditingChild={startEditingSavedChild}
                        onCancelEditing={() => setEditingSavedCardId(null)}
                        onCancelEditingChild={() => setEditingSavedChildId(null)}
                        onSubmitEdit={submitEditCard}
                        onSubmitEditChild={submitEditChild}
                        onDelete={(id) => {
                          setDeletedId(id);
                          setEditingSavedCardId(null);
                          deleteCardMutation.mutate(id);
                          setTimeout(() => setDeletedId(null), 5000);
                        }}
                        onDeleteChild={(id) => {
                          setDeletedId(id);
                          setEditingSavedChildId(null);
                          deleteChildMutation.mutate(id);
                          setTimeout(() => setDeletedId(null), 5000);
                        }}
                        isSubmitting={patchCardMutation.isPending || patchChildMutation.isPending}
                        onUpdateParentFromMessyText={handleUpdateParentFromMessyText}
                        onUpdateChildFromMessyText={handleUpdateChildFromMessyText}
                        isUpdatingFromMessyText={isUpdatingFromMessyText}
                      />
                    ))}
                  </motion.div>
                )}
              </>
            )}
          </div>
          <div className="flex-shrink-0 pt-3 sm:pt-4 pb-1 flex justify-end border-t border-border/50 mt-2">
            <Button
              onClick={() => {
                setSaveError(null);
                setSaveModalOpen(true);
              }}
              disabled={!hasV1Families}
              className="w-full sm:w-auto min-h-[2.75rem] touch-manipulation"
            >
              Save Cards
            </Button>
          </div>
        </div>
      </div>

      <SaveCardsModal
        open={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        onConfirm={handleSaveCards}
        isSaving={isSavingAll}
        error={saveError}
      />
    </motion.div>
  );
}
