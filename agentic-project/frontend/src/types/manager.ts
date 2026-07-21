export interface SuggestedAim {
  aim: string;
  dataset: string;
  role: string;
  kpi_value?: string;
  display_number?: number;
  confirm_id?: string;
  description?: string;
  benefits?: string;
  columns?: { dataset: string; names: string[] }[];
  datasets?: string[];
}

export interface TurnUi {
  phase?: string;
  line?: string;
  missing?: string[];
  plan?: { aims?: string[]; benefits?: string };
  proposals?: Record<string, unknown>[];
  selected_proposal_index?: number | null;
  proposal_counter?: number;
  saved_plans?: { id?: string; label?: string; aims?: string[] }[];
  scope_pending?: boolean;
  done?: boolean;
  executed?: boolean;
  next_step?: string | null;
  suggested_aims?: SuggestedAim[];
  custom_aims?: { aim: string; display_number?: number; confirm_id?: string }[];
  explanation?: string;
  planner_payload?: {
    line_name?: string;
  datasets?: { name: string; table?: string; role?: string; description?: string; data_earliest_ts?: string | null }[];
    task_definition?: {
      aims?: string[];
      alias_name?: string;
      notes?: string;
      time_range?: { start?: string; end?: string };
      datasets_in_scope?: string[];
      datasets_excluded?: string[];
    };
    time_range?: { start?: string; end?: string };
    datasets_in_scope?: string[];
    datasets_excluded?: string[];
    join_catalog?: { from_dataset?: string; to_dataset?: string; on?: string[] }[];
  };
  proposal_provenance?: { suggestedAim: string; fulfilledByProposalIds: number[] }[];
  actions?: { label: string; msg: string; primary?: boolean }[];
  show_change?: boolean;
  time_default_notice?: string;
}

export interface SchemaSnapshot {
  line?: string;
  line_match?: { mention?: string; canonical?: string; source?: string };
  datasets?: { name: string; table?: string; role?: string; description?: string; data_earliest_ts?: string | null }[];
  suggested_aims?: SuggestedAim[];
  datasets_in_scope?: string[];
  datasets_excluded?: string[];
  columns?: { dataset: string; name: string; datatype?: string; meaning?: string }[];
  joins?: {
    from_dataset?: string;
    to_dataset?: string;
    on?: string[];
    note?: string | null;
  }[];
  time?: { start: string; end: string };
  time_pending?: string | null;
  no_time_filter?: boolean;
  data_available_from?: string | null;
}

export interface Turn {
  turn_index?: number;
  user: string;
  agent: string;
  ui: TurnUi | null;
  schema: SchemaSnapshot | null;
  created_at?: string;
  description?: string | null;
  benefits?: string | null;
  columns?: { dataset: string; name: string }[] | null;
  analysis_actions?: AnalysisAction[];
}

export interface SessionMeta {
  session_id: string;
  line_name?: string;
  title?: string | null;
  mode?: string;
  phase?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SessionListItem {
  session_id: string;
  line_name?: string;
  title?: string | null;
  mode?: string;
  phase?: string;
  status?: string;
}

export interface SessionDetail {
  session: SessionMeta;
  turns: Turn[];
}

export interface MessageResponse {
  session_id: string;
  turn_index?: number;
  agent_message?: string;
  next_step?: string | null;
  phase?: string;
  status?: string;
  ui?: TurnUi | null;
  schema?: SchemaSnapshot | null;
  done?: boolean;
  description?: string | null;
  benefits?: string | null;
  columns?: { dataset: string; name: string }[] | null;
  aim_proposals?: { aim: string; description: string; datasets: string[] }[];
  analysis_actions?: AnalysisAction[];
}

export interface AnalysisAction {
  name: string;
  description: string;
  datasets: string[];
}

export interface ChartConfig {
  chartType: "composed" | "stackedArea" | "treemap" | "radialBar" | "funnel" | "sunburst" | "scatter" | "radar" | "bar" | "line" | "area" | "pie";
  xKey: string;
  yKeys: string[];
  reason?: string;
  xLabel?: string;
  yLabel?: string;
  howToRead?: string;
}

export interface ChartSuggestions {
  advanced: ChartConfig[];
  basic: ChartConfig[];
}
