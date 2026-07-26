export interface ParsedSuggestion {
  name: string;
  goal?: string;
  datasets: string[];
  columns: string[];
  explanation?: string;
  insight?: string;
}

export interface ParsedSuggestions {
  intro: string;
  suggestions: ParsedSuggestion[];
}

// Matches "1. **Name**: Title" AND the looser "1. **Title**" (model sometimes
// bolds the title alone instead of using a "Name:" label).
const ITEM_START = /^\s*\d+[.)]\s*\*\*/gm;
const LABELED_LINE = /^\*\*([A-Za-z][A-Za-z ]*)\*\*\s*:\s*(.*)$/;
const BARE_BOLD_LINE = /^\*\*(.+?)\*\*\s*$/;
// Fields the model tends to spread across multiple lines instead of one
// comma-separated line — continuation lines get comma-joined, not space-joined.
const LIST_FIELDS = new Set(["datasets", "columns"]);

function splitCsv(value: string): string[] {
  // Strip inline bold markers — the model sometimes bolds names inside Datasets/Columns too.
  return value.split(",").map((v) => v.replace(/\*\*/g, "").trim()).filter(Boolean);
}

/** Parses the SUGGEST-mode reply format (numbered list of Name/Goal/Datasets/Columns/Explanation/Expected Insight)
 * into structured cards. Tolerant of the model bolding the title alone (no "Name:" label) and of
 * Datasets/Columns being split one-per-line instead of comma-separated. Returns null if the text
 * doesn't look like this format at all, so callers can fall back to plain markdown. */
export function parseSuggestions(text: string): ParsedSuggestions | null {
  if (!text) return null;

  const starts: number[] = [];
  const re = new RegExp(ITEM_START);
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) starts.push(m.index);
  if (starts.length === 0) return null;

  const intro = text.slice(0, starts[0]).trim();
  const chunks = starts.map((start, i) =>
    text.slice(start, i + 1 < starts.length ? starts[i + 1] : text.length)
  );

  const suggestions: ParsedSuggestion[] = [];
  for (const chunk of chunks) {
    const lines = chunk
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
    if (lines.length > 0) lines[0] = lines[0].replace(/^\d+[.)]\s*/, "");

    const fields: Record<string, string> = {};
    let currentKey: string | null = null;

    lines.forEach((line, i) => {
      const labeled = line.match(LABELED_LINE);
      if (labeled) {
        currentKey = labeled[1].trim().toLowerCase();
        fields[currentKey] = labeled[2].trim();
        return;
      }
      if (i === 0) {
        const bare = line.match(BARE_BOLD_LINE);
        if (bare) {
          currentKey = "name";
          fields.name = bare[1].trim();
          return;
        }
      }
      if (currentKey) {
        fields[currentKey] = LIST_FIELDS.has(currentKey)
          ? `${fields[currentKey]}, ${line}`
          : `${fields[currentKey]} ${line}`.trim();
      }
    });

    if (!fields["name"]) continue;
    suggestions.push({
      name: fields["name"].replace(/\*\*/g, ""),
      goal: fields["goal"],
      datasets: fields["datasets"] ? splitCsv(fields["datasets"]) : [],
      columns: fields["columns"] ? splitCsv(fields["columns"]) : [],
      explanation: fields["explanation"],
      insight: fields["expected insight"],
    });
  }

  if (suggestions.length === 0) return null;
  return { intro, suggestions };
}
