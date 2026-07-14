export interface TurnUi {
  phase?: string;
  line?: string;
  missing?: string[];
  plan?: { aims?: string[]; benefits?: string };
  proposals?: Record<string, unknown>[];
  saved_plans?: { id?: string; label?: string; aims?: string[] }[];
  scope_pending?: boolean;
  done?: boolean;
  next_step?: string | null;
  suggested_aims?: {
    aim: string;
    dataset: string;
    role: string;
    kpi_value?: string;
  }[];
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
  selectedProposalIndex?: number;
  proposal_provenance?: { suggestedAim: string; fulfilledByProposalIds: number[] }[];
  actions?: { label: string; msg: string; primary?: boolean }[];
  show_change?: boolean;
  time_default_notice?: string;
}

export interface SchemaSnapshot {
  line?: string;
  line_match?: { mention?: string; canonical?: string; source?: string };
  datasets?: { name: string; table?: string; role?: string; description?: string }[];
  suggested_aims?: {
    aim: string;
    dataset: string;
    role: string;
    kpi_value?: string;
  }[];
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
}
