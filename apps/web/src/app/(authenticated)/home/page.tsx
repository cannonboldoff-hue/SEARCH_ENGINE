"use client";

import { useRef, useEffect, useCallback } from "react";
import { Send, Mic, Square } from "lucide-react";
import { useSearch } from "@/contexts/search-context";
import { SearchResults } from "@/components/search";
import { ErrorMessage } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useVoiceInput } from "@/components/builder";

const SUGGESTIONS = [
  "Software engineers in San Francisco",
  "Product managers open to work",
  "Designers with UX experience",
  "Data scientists in NYC",
  "Marketing leads at startups",
];

export default function HomePage() {
  const {
    query,
    setQuery,
    searchId,
    people: searchPeople,
    error: searchError,
    openToWorkOnly,
    setOpenToWorkOnly,
    performSearch,
    performSearchWithQuery,
    isSearching,
  } = useSearch();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const searchTranscriptRef = useRef("");
  const wasRecordingRef = useRef(false);

  const handleVoiceTranscript = useCallback(
    (text: string) => {
      setQuery(text);
      searchTranscriptRef.current = text;
    },
    [setQuery]
  );

  const {
    isRecording,
    isConnectingRecorder,
    toggleRecording,
    recordingError,
  } = useVoiceInput(handleVoiceTranscript);

  const autoResize = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    const id = setTimeout(autoResize, 0);
    return () => clearTimeout(id);
  }, [query, autoResize]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      performSearch();
    }
  };

  const handleSuggestionClick = (text: string) => {
    performSearchWithQuery(text);
  };

  // Run search when voice recording stops and we have transcript (Sarvam AI via API)
  useEffect(() => {
    const wasRecording = wasRecordingRef.current;
    wasRecordingRef.current = isRecording || isConnectingRecorder;
    if (wasRecording && !isRecording && !isConnectingRecorder) {
      const text = searchTranscriptRef.current?.trim();
      if (text) performSearchWithQuery(text);
    }
  }, [isRecording, isConnectingRecorder, performSearchWithQuery]);

  const hasSearched = !!searchId;
  const showEmptyState = !hasSearched;

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] -my-6 -mx-4 sm:-mx-0">
      {/* Scrollable content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {searchError && (
          <div className="container max-w-3xl mx-auto px-4 pt-4">
            <ErrorMessage message={searchError} />
          </div>
        )}

        {showEmptyState ? (
          <div className="flex flex-col items-center justify-center min-h-[50vh] px-4 py-12">
            <h1 className="text-2xl sm:text-3xl font-semibold text-foreground text-center mb-2">
              Who are you looking for?
            </h1>
            <p className="text-muted-foreground text-sm text-center mb-8 max-w-md">
              Describe the people you want to find. Try skills, roles, locations, or open-to-work.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-xl">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleSuggestionClick(s)}
                  className="px-4 py-2 rounded-full text-sm bg-muted/80 hover:bg-muted text-foreground/90 hover:text-foreground border border-border/60 hover:border-border transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="container max-w-6xl mx-auto px-4 py-6 space-y-4">
            <SearchResults searchId={searchId} people={searchPeople} />
          </div>
        )}
      </div>

      {/* Bottom input bar - ChatGPT style */}
      <div className="flex-shrink-0 border-t border-border bg-background">
        <div className="container max-w-3xl mx-auto px-4 py-4">
          <form
            onSubmit={handleSubmit}
            className="relative flex items-end gap-2 rounded-2xl border border-border bg-muted/30 hover:bg-muted/50 focus-within:bg-muted/50 focus-within:ring-1 focus-within:ring-ring/30 transition-all shadow-sm"
          >
            <div className="absolute left-4 bottom-3 flex items-center gap-2">
              <input
                type="checkbox"
                id="home_open_to_work"
                checked={openToWorkOnly}
                onChange={(e) => setOpenToWorkOnly(e.target.checked)}
                className="rounded border-border accent-foreground h-3.5 w-3.5"
              />
              <Label htmlFor="home_open_to_work" className="text-xs text-muted-foreground cursor-pointer">
                Open to work only
              </Label>
            </div>
            <textarea
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe who you're looking for..."
              rows={1}
              className="flex-1 min-h-[52px] max-h-[200px] resize-none rounded-2xl bg-transparent pl-36 pr-24 py-3.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none overflow-y-auto"
              style={{ maxHeight: 200 }}
            />
            <div className="absolute right-2 bottom-2 flex items-center gap-1">
              <Button
                type="button"
                size="icon"
                variant={isRecording ? "destructive" : "ghost"}
                disabled={isSearching || isConnectingRecorder}
                onClick={toggleRecording}
                title={isRecording ? "Stop listening" : "Voice search (Sarvam AI)"}
                className="h-9 w-9 rounded-xl shrink-0"
              >
                {isConnectingRecorder ? (
                  <span className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
                ) : isRecording ? (
                  <Square className="h-4 w-4" aria-hidden />
                ) : (
                  <Mic className="h-4 w-4" aria-hidden />
                )}
              </Button>
              <Button
                type="submit"
                size="icon"
                disabled={isSearching || !query.trim()}
                className="h-9 w-9 rounded-xl shrink-0"
              >
                {isSearching ? (
                  <span className="h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </form>
          <p className={`text-[11px] text-center mt-2 ${recordingError ? "text-destructive" : "text-muted-foreground"}`}>
            {recordingError || "Press Enter to search"}
          </p>
        </div>
      </div>
    </div>
  );
}
