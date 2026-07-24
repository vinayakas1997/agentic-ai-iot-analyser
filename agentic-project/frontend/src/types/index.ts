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
