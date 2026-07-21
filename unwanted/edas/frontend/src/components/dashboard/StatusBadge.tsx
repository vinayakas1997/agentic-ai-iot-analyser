export default function StatusBadge({ status }: { status?: string }) {
  const label = status || "pending";
  const s = label.toLowerCase();
  const color =
    s.includes("fail") || s.includes("error")
      ? "bg-red-950 text-red-400"
      : s.includes("complete") || s.includes("success")
        ? "bg-green-950 text-success"
        : "bg-zinc-800 text-muted";
  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded-full ${color}`}>{label}</span>
  );
}
