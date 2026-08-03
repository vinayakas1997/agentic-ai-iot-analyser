export interface AimItem {
  aim: string;
  display_number?: number;
  confirm_id?: string;
  dataset?: string;
  role?: string;
  kpi_value?: string;
  description?: string;
  benefits?: string;
  columns?: { dataset: string; names: string[] }[];
  datasets?: string[];
}

export interface DatasetInfo {
  line_name: string;
  dataset_name: string;
  description: string | null;
  table: string | null;
  column_definitions: { name: string; datatype: string; meaning?: string }[];
  role: string | null;
  join_hints: any;
  suggested_aims: any;
  synonyms: string[] | null;
  /** Origin of this entry: a global-registry dataset vs. the user's own uploaded CSV.
   *  Lets the UI keep the two lists visually and logically separate instead of
   *  merging them into one untagged array. */
  source?: "registry" | "personal";
}

export interface ResolvedLine {
  lineName: string;
  canonical: string;
  resolved: boolean;
  candidates: string[];
  datasets: DatasetInfo[];
}

export interface SelectedAim {
  id: string;
  lineName: string;
  aim: string;
  datasets_used: string[];
  source: "suggested" | "research";
  how_we_will_do_it?: string;
  joins?: string;
}

export interface BucketItem {
  id: string;
  lineName: string;
  aim: string;
  datasets_used: string[];
  status: "pending" | "working" | "completed" | "failed";
  version?: number;
  result?: any;
}

export interface SessionInfo {
  session_id: string;
  title: string;
  phase: string;
  status: string;
  mode?: string;
}

export interface NewResearchResult {
  aim: string;
  how_we_will_do_it: string;
  datasets_used: string[];
  joins: string | null;
}

export interface ColumnProfile {
  datatype: string;
  null_pct: number;
  distinct_count: number;
  is_constant: boolean;
  zero_pct: number | null;
  min: string | null;
  max: string | null;
  common_samples: string[];
}

export interface ColumnDraft {
  name: string;
  original_name?: string;
  datatype: string;
  meaning: string;
}

export interface UploadedFileDraft {
  dataset_id: number;
  dataset_name: string;
  table_name: string;
  filename: string;
  columns: ColumnDraft[];
  profiling: Record<string, ColumnProfile>;
  row_count: number;
  warnings: string[];
}

export interface UploadFailure {
  filename: string;
  errors: string[];
}

export interface ColumnTemplate {
  id: number;
  template_name: string;
  column_definitions: ColumnDraft[];
  created_at?: string | null;
}

export interface TemplateMatch {
  id: number;
  template_name: string;
  match_pct: number;
  matched_columns: { name: string; meaning: string }[];
}

export interface AnswerTemplate {
  id: number;
  template_name: string;
  format_spec: string;
  created_at?: string | null;
}

export interface PersonalDataset {
  id: number;
  dataset_name: string;
  table_name: string;
  original_filename: string;
  description: string | null;
  column_definitions: ColumnDraft[];
  column_profiling: Record<string, ColumnProfile>;
  row_count: number;
  status: "draft" | "active";
}
