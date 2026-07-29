import { FormEvent, KeyboardEvent, Fragment, useState, useRef } from "react";
import { btnPrimary, panelClass } from "../lib/styles";
import { useSessionStore, useIsDone, useIsLive } from "../stores/sessionStore";
import { useUiStore } from "../stores/uiStore";

export default function ChatSection() {
  const turns = useSessionStore((s) => s.turns);
  const loading = useSessionStore((s) => s.loading);
  const sendUserMessage = useSessionStore((s) => s.sendUserMessage);
  const uploadCSV = useSessionStore((s) => s.uploadCSV);
  const selectedTurnIndex = useUiStore((s) => s.selectedTurnIndex);
  const selectTurn = useUiStore((s) => s.selectTurn);
  const isLive = useIsLive();
  const isDone = useIsDone();
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (selectedFile) {
      try {
        await uploadCSV(selectedFile);
        setSelectedFile(null);
        fileInputRef.current!.value = "";
      } catch (err) {
        console.error("CSV upload failed:", err);
      }
      return;
    }
    if (!input.trim() || loading || isDone) return;
    const text = input;
    setInput("");
    await sendUserMessage(text);
  };

  return (
    <section className={`${panelClass} order-2 lg:order-none`}>
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h2 className="text-base font-semibold font-display">Chat</h2>
        {isDone && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-950 text-success">Completed</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 pr-1 mb-3">
        {turns.length === 0 && (
          <p className="text-muted text-sm">
            What would you like to analyze? Try a line name like Vinayaka or fruits test.
          </p>
        )}
        {turns.map((turn, i) => (
          <Fragment key={turn.turn_index ?? i}>
            {i > 0 && <hr className="border-t border-border/30 my-3" />}
            <div
              className={`p-2 rounded-lg cursor-pointer border-l-2 ${
                i === selectedTurnIndex
                  ? "ring-1 ring-accent bg-blue-500/10 border-l-accent"
                  : i % 2 === 1
                    ? "bg-stripe-odd border-l-rail/30"
                    : "border-l-transparent"
              } ${i !== selectedTurnIndex ? "hover:bg-white/[0.02]" : ""}`}
              onClick={() => selectTurn(i)}
              onKeyDown={(e: KeyboardEvent) => e.key === "Enter" && selectTurn(i)}
              role="button"
              tabIndex={0}
            >
              {turn.user && (
                <div className="mb-2 ml-auto max-w-[95%] rounded-xl bg-blue-900/40 p-3">
                  <span className="text-[0.7rem] text-muted block mb-1">You</span>
                  <p className="text-sm m-0">{turn.user}</p>
                </div>
              )}
              {turn.agent && (
                <div className="mb-2 max-w-[95%] rounded-xl bg-zinc-800 p-3">
                  <span className="text-[0.7rem] text-muted block mb-1">Manager</span>
                  <p className="text-sm m-0 leading-relaxed whitespace-pre-wrap">{turn.agent}</p>
                </div>
              )}
              {turn.ui?.next_step && (
                <div className="max-w-[95%] rounded-xl border border-green-900 bg-cta p-3">
                  <span className="text-[0.7rem] text-muted block mb-1">Next</span>
                  <p className="text-sm m-0 leading-relaxed whitespace-pre-wrap">{turn.ui.next_step}</p>
                </div>
              )}
            </div>
          </Fragment>
        ))}
        {loading && <p className="text-muted text-sm">Thinking…</p>}
      </div>

      <form className="flex gap-2 shrink-0" onSubmit={handleSubmit}>
        <input
          type="text"
          className="flex-1 rounded-lg border border-border bg-app text-text px-3 py-2 text-sm"
          placeholder={isDone ? "Session complete" : "Ask anything…"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading || isDone || !isLive || !!selectedFile}
        />
        <input
          type="file"
          accept=".csv"
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          onClick={handleFileSelect}
          disabled={loading || isDone || !isLive}
          className="bg-accent hover:bg-[#1d8cf0] text-white rounded-lg px-3 py-2 text-sm font-medium shadow-[0_4px_0_0_#0f5fa3] active:translate-y-1 active:shadow-[0_1px_0_0_#0f5fa3] transition-all duration-75 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {selectedFile ? selectedFile.name : "Upload CSV"}
        </button>
        <button
          type="submit"
          className={btnPrimary}
          disabled={loading || isDone || (!input.trim() && !selectedFile)}
        >
          {selectedFile ? "Upload" : "Send"}
        </button>
      </form>
      {!isLive && turns.length > 0 && (
        <p className="text-muted text-xs mt-2 shrink-0">
          Viewing step {selectedTurnIndex + 1}. Select latest turn to send messages.
        </p>
      )}
    </section>
  );
}
