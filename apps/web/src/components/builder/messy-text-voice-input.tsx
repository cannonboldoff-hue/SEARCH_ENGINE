import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AUTH_TOKEN_KEY } from "@/lib/auth-flow";
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

export function useVoiceInput(onChange: (text: string) => void) {
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
  const currentValueRef = useRef("");

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
            const next = appendTranscriptText(currentValueRef.current, delta);
            currentValueRef.current = next;
            onChange(next);
          }
          lastServerTranscriptRef.current = transcript;
          return;
        }

        if (msg.type === "error") {
          setRecordingError(msg.detail || "Voice transcription failed.");
        }
      };

      ws.onerror = () => {
        stopRecording(false);
        setRecordingError("Connection error with voice service.");
      };

      ws.onclose = () => {
        setIsRecording(false);
      };

      processor.onaudioprocess = (event) => {
        const socket = recorderSocketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) return;

        const pcm = event.inputBuffer.getChannelData(0);
        const downsampled = downsampleTo16k(pcm, audioContext.sampleRate);
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
  }, [cleanupAudioGraph, isConnectingRecorder, isRecording, onChange]);

  const toggleRecording = useCallback(() => {
    if (isRecording || isConnectingRecorder) {
      stopRecording(true);
      return;
    }
    void startRecording();
  }, [isConnectingRecorder, isRecording, startRecording, stopRecording]);

  return {
    isRecording,
    isConnectingRecorder,
    toggleRecording,
    liveTranscript,
    recordingError,
  };
}

interface MessyTextVoiceInputProps {
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
  rows?: number;
  showButton?: boolean;
  hideVoiceButton?: boolean;
}

interface VoiceButtonProps {
  isRecording: boolean;
  isConnectingRecorder: boolean;
  onToggle: () => void;
}

export function VoiceButton({
  isRecording,
  isConnectingRecorder,
  onToggle,
}: VoiceButtonProps) {
  return (
    <Button
      type="button"
      size="sm"
      variant={isRecording ? "destructive" : "outline"}
      onClick={onToggle}
      disabled={isConnectingRecorder}
      className="h-8 px-2"
    >
      {isRecording ? <Square className="h-3.5 w-3.5 mr-1" /> : <Mic className="h-3.5 w-3.5 mr-1" />}
      {isConnectingRecorder ? "Connecting..." : isRecording ? "Stop Voice" : "Voice"}
    </Button>
  );
}

export function MessyTextVoiceInput({
  value,
  onChange,
  placeholder,
  rows = 2,
  showButton = true,
  hideVoiceButton = false,
}: MessyTextVoiceInputProps) {
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
  const currentValueRef = useRef(value);

  useEffect(() => {
    currentValueRef.current = value;
  }, [value]);

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
            const next = appendTranscriptText(currentValueRef.current, delta);
            currentValueRef.current = next;
            onChange(next);
          }
          lastServerTranscriptRef.current = transcript;
          return;
        }

        if (msg.type === "error") {
          setRecordingError(msg.detail || "Voice transcription failed.");
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
  }, [cleanupAudioGraph, isConnectingRecorder, isRecording, onChange]);

  const toggleRecording = useCallback(() => {
    if (isRecording || isConnectingRecorder) {
      stopRecording(true);
      return;
    }
    void startRecording();
  }, [isConnectingRecorder, isRecording, startRecording, stopRecording]);

  return (
    <div className="space-y-2">
      {isRecording && !isConnectingRecorder && (
        <p className="text-[11px] text-muted-foreground">Listening...</p>
      )}

      {liveTranscript && (
        <p className="text-[11px] text-muted-foreground truncate">Live: {liveTranscript}</p>
      )}
      {recordingError && (
        <p className="text-[11px] text-destructive">{recordingError}</p>
      )}

      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="text-sm resize-y bg-background"
      />
    </div>
  );
}

export function useVoiceRecording(
  value: string,
  onChange: (next: string) => void
) {
  const [isRecording, setIsRecording] = useState(false);
  const [isConnectingRecorder, setIsConnectingRecorder] = useState(false);

  const recorderSocketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const lastServerTranscriptRef = useRef("");
  const currentValueRef = useRef(value);

  useEffect(() => {
    currentValueRef.current = value;
  }, [value]);

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
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  const stopRecording = useCallback(
    (final: boolean) => {
      setIsRecording(false);
      cleanupAudioGraph();

      const mediaStream = mediaStreamRef.current;
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }

      const ws = recorderSocketRef.current;
      if (ws && ws.readyState < WebSocket.CLOSING) {
        if (final) {
          ws.send(JSON.stringify({ type: "end_stream" }));
        }
        ws.close();
      }
      recorderSocketRef.current = null;
    },
    [cleanupAudioGraph]
  );

  const startRecording = useCallback(async () => {
    setIsConnectingRecorder(true);

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

          const previous = lastServerTranscriptRef.current;
          const cleaned = previous ? transcript.replace(new RegExp(`^${previous}\\s*`), "") : transcript;
          lastServerTranscriptRef.current = transcript;

          onChange(appendTranscriptText(currentValueRef.current, cleaned));
        }
      };

      ws.onerror = () => {
        stopRecording(false);
      };

      ws.onclose = () => {
        setIsRecording(false);
      };

      processor.onaudioprocess = (event) => {
        const socket = recorderSocketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) return;

        const pcm = event.inputBuffer.getChannelData(0);
        const downsampled = downsampleTo16k(pcm, audioContext.sampleRate);
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
    }
  }, [cleanupAudioGraph, isConnectingRecorder, isRecording, onChange]);

  const toggleRecording = useCallback(() => {
    if (isRecording || isConnectingRecorder) {
      stopRecording(true);
      return;
    }
    void startRecording();
  }, [isConnectingRecorder, isRecording, startRecording, stopRecording]);

  return {
    isRecording,
    isConnectingRecorder,
    toggleRecording,
  };
}

export function MessyTextVoiceInputLegacy({
  value,
  onChange,
  placeholder,
  rows = 2,
}: MessyTextVoiceInputProps) {
  return (
    <MessyTextVoiceInput
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      rows={rows}
      showButton={false}
      hideVoiceButton={true}
    />
  );
}

