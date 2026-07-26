import { useUploadStore } from "../stores/uploadStore";

export default function ProcessingOverlay() {
  const isProcessing = useUploadStore((s) => s.isProcessing);
  const label = useUploadStore((s) => s.processingLabel);

  if (!isProcessing) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-bg-deep/40 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-3 rounded-2xl border-2 border-border bg-surface-1 px-8 py-6 shadow-xl">
        <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin" />
        <div className="text-sm font-medium text-text">{label || "Processing..."}</div>
      </div>
    </div>
  );
}
