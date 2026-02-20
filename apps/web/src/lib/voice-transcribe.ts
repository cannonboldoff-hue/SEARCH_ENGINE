/**
 * Shared voice transcription helpers (WebSocket URL, audio downsampling, PCM encoding).
 * Used by builder page and MessyTextVoiceInput component.
 */

import { API_BASE } from "@/lib/constants";

export const STREAM_SAMPLE_RATE = 16000;
export const STREAM_PROCESSOR_BUFFER = 4096;

export type StreamServerMessage =
  | { type: "transcript"; transcript?: string }
  | { type: "error"; detail?: string }
  | { type: "event"; event?: unknown };

export function buildTranscribeWsUrl(token: string): string {
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

export function downsampleTo16k(
  input: Float32Array,
  inputSampleRate: number
): Float32Array {
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

export function float32ToPcm16Buffer(floatBuffer: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(floatBuffer.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < floatBuffer.length; i += 1) {
    const s = Math.max(-1, Math.min(1, floatBuffer[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...Array.from(chunk));
  }
  return btoa(binary);
}

export function appendTranscriptText(current: string, nextText: string): string {
  const clean = nextText.trim();
  if (!clean) return current;
  if (!current.trim()) return clean;
  return `${current}${/\s$/.test(current) ? "" : " "}${clean}`;
}
