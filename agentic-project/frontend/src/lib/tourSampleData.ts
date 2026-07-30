import type { QueryResultState } from "../sections/QueryActions";
import type { UploadedFileDraft } from "../types";

export const TOUR_DATASET_NAME = "production_data";

export const TOUR_AIM_NAME = "defect rate by machine";

export const FAKE_SEARCH_RESULTS = [
  { name: "production_data", nameKey: "tour.datasetProduction", cols: 6, checked: true, line: "PROD_LINE_01", lineKey: "tour.lineProd01" },
  { name: "equipment_logs", nameKey: "tour.datasetEquipment", cols: 8, checked: false, line: "MAINT_LINE_02", lineKey: "tour.lineMaint02" },
];

export const FAKE_AIM = {
  aim: "defect rate by machine",
  aimKey: "tour.fakeAimName",
  description: "Analyze defect rates across production machines to identify underperforming equipment",
  descriptionKey: "tour.fakeAimDesc",
};

export const TOUR_MESSAGE = "What analysis can be done on this dataset?";

export const TOUR_QUESTIONS = [
  { key: "tour.question1", text: "What is the defect rate by machine?" },
  { key: "tour.question2", text: "Show me production output trends" },
  { key: "tour.question3", text: "Which machine has the highest downtime?" },
];

export const TOUR_SAMPLE_RESULT: QueryResultState = {
  loading: false,
  sql: `SELECT machine_id, SUM(units_produced) AS total_output,\n  ROUND(AVG(defect_count) * 100.0 / NULLIF(AVG(units_produced), 0), 1) AS defect_rate\nFROM production_logs\nGROUP BY machine_id\nORDER BY defect_rate DESC`,
  columns: ["machine_id", "total_output", "defect_rate"],
  column_types: ["text", "bigint", "numeric"],
  rows: [
    { machine_id: "CNC-002", total_output: 3800, defect_rate: 3.5 },
    { machine_id: "CNC-004", total_output: 4100, defect_rate: 2.8 },
    { machine_id: "CNC-001", total_output: 4500, defect_rate: 2.1 },
    { machine_id: "CNC-003", total_output: 4200, defect_rate: 1.8 },
    { machine_id: "CNC-005", total_output: 3900, defect_rate: 1.2 },
  ],
  row_count: 5,
  chart_suggestions: {
    advanced: [],
    basic: [
      {
        chartType: "bar",
        xKey: "machine_id",
        yKeys: ["defect_rate"],
        reason: "Compare defect rates across machines",
        xLabel: "Machine",
        yLabel: "Defect Rate (%)",
      },
    ],
  },
};

export interface DemoChartData {
  type: string;
  description: string;
  data: Record<string, unknown>[];
  xKey: string;
  yKeys: string[];
}

export function mockDraft(filledMeanings: Record<string, string>): UploadedFileDraft {
  const baseCols = [
    { name: "date", datatype: "date", meaning: "" },
    { name: "machine_id", datatype: "text", meaning: "" },
    { name: "product_code", datatype: "text", meaning: "" },
    { name: "units_produced", datatype: "integer", meaning: "" },
    { name: "defect_count", datatype: "integer", meaning: "Number of defective units" },
    { name: "cycle_time_sec", datatype: "numeric", meaning: "" },
  ];
  return {
    dataset_id: 999,
    dataset_name: "sample_upload",
    table_name: "sample_upload",
    filename: "production_data.csv",
    columns: baseCols.map((c) => ({ ...c, meaning: filledMeanings[c.name] ?? c.meaning })),
    profiling: Object.fromEntries(
      baseCols.map((c) => [
        c.name,
        {
          datatype: c.datatype,
          null_pct: c.name === "cycle_time_sec" ? 0.02 : 0,
          distinct_count: 0,
          is_constant: false,
          zero_pct: null,
          min: null,
          max: null,
          common_samples: [] as string[],
        },
      ])
    ),
    row_count: 150,
    warnings: ["Column 'cycle_time_sec' has 2% null values"],
  };
}

export const LLM_FILL_STAGES: Record<string, string>[] = [
  { machine_id: "Machine identifier code", product_code: "Product being manufactured" },
  { units_produced: "Total units produced in shift" },
];

export const LLM_TYPING_COLUMNS: Record<string, string> = {
  machine_id: "Machine identifier code",
  product_code: "Product being manufactured",
  units_produced: "Total units produced in shift",
};

export const CSV_PREVIEW_LINES = [
  "date,machine_id,product_code,units_produced,defect_count,cycle_time_sec",
  "2024-01-15,CNC-001,A-100,150,3,45.2",
  "2024-01-16,CNC-002,A-100,200,5,48.7",
  "2024-01-17,CNC-001,B-200,120,1,42.1",
];

export const DEFS_PREVIEW_LINES = [
  "date,Production date",
  "machine_id,Machine identifier code",
  "product_code,Product being manufactured",
  "units_produced,Total units produced in shift",
  "defect_count,Number of defective units",
  "cycle_time_sec,Cycle time in seconds",
];

export const DEMO_CHARTS: DemoChartData[] = [
  {
    type: "Bar",
    description:
      "Bar charts compare values across categories. Each bar height represents a value, making it easy to see which machine has the highest output or defect rate at a glance.",
    xKey: "machine",
    yKeys: ["output"],
    data: [
      { machine: "CNC-001", output: 4500 },
      { machine: "CNC-002", output: 3800 },
      { machine: "CNC-003", output: 4200 },
      { machine: "CNC-004", output: 4100 },
      { machine: "CNC-005", output: 3900 },
    ],
  },
  {
    type: "Line",
    description:
      "Line charts show trends over time. The connected points make it easy to see patterns — going up means increasing production, going down means decline.",
    xKey: "week",
    yKeys: ["output"],
    data: [
      { week: "W1", output: 1200 },
      { week: "W2", output: 1900 },
      { week: "W3", output: 1500 },
      { week: "W4", output: 2200 },
      { week: "W5", output: 2800 },
      { week: "W6", output: 2500 },
    ],
  },
  {
    type: "Pie",
    description:
      "Pie charts show proportions of a whole. Each slice represents a category's share — bigger slice means more defects attributed to that machine.",
    xKey: "machine",
    yKeys: ["defects"],
    data: [
      { machine: "CNC-001", defects: 35 },
      { machine: "CNC-002", defects: 25 },
      { machine: "CNC-003", defects: 20 },
      { machine: "CNC-004", defects: 12 },
      { machine: "CNC-005", defects: 8 },
    ],
  },
];
