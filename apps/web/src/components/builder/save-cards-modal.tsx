"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ErrorMessage } from "@/components/error-message";

type SaveCardsModalProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isSaving: boolean;
  error: string | null;
};

export function SaveCardsModal({
  open,
  onClose,
  onConfirm,
  isSaving,
  error,
}: SaveCardsModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            className="rounded-xl glass border border-border p-6 max-w-md w-full mx-4 shadow-xl glow-ring depth-shadow-lg"
            style={{ transformStyle: "preserve-3d", perspective: 1200 }}
            initial={{ opacity: 0, scale: 0.92, y: 24, rotateX: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0, rotateX: 0 }}
            exit={{ opacity: 0, scale: 0.92, rotateX: 12 }}
            transition={{ type: "spring", stiffness: 280, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-foreground">Save experience cards?</h3>
            <p className="text-sm text-muted-foreground mt-2">
              This will update your searchable profile. Saved cards become visible to searchers.
            </p>
            {error && (
              <div className="mt-3">
                <ErrorMessage message={error} />
              </div>
            )}
            <div className="flex gap-2 mt-6 justify-end">
              <Button variant="outline" onClick={onClose} disabled={isSaving}>
                Cancel
              </Button>
              <Button onClick={onConfirm} disabled={isSaving}>
                {isSaving ? "Saving…" : "Confirm Save"}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
