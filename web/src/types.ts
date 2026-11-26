export type StepType = "start" | "task" | "decision" | "approval" | "notification" | "end";
export type StepStatus = "pending" | "in_progress" | "done" | "blocked" | "skipped";

export interface WorkflowStep {
  id: string;
  title: string;
  description: string;
  step_type: StepType;
  owner_role: string | null;
  depends_on: string[];
  condition: string | null;
  on_true: string | null;
  on_false: string | null;
  estimated_duration: string | null;
  system_hint: string | null;
  status: StepStatus;
  notes: string;
  rationale: string | null;
}

export interface Workflow {
  id: string;
  title: string;
  domain: string;
  summary: string;
  steps: WorkflowStep[];
  assumptions: string[];
  risks: string[];
  missing_information: string[];
  suggested_improvements: string[];
  created_at: string;
}

export interface RunRecord {
  id: string;
  project_id: string;
  started_at: string;
  finished_at: string | null;
  outcome: string;
  transitions: { step_id: string; status: StepStatus; notes: string; at: string }[];
  notes: string;
}

export interface Project {
  id: string;
  owner_id: string | null;
  workflow: Workflow;
  title: string;
  metadata: {
    category: string;
    prompt: string;
    provider: string;
    requested_provider: string | null;
    model: string | null;
    tokens_in: number;
    tokens_out: number;
    estimated_cost_usd: number;
    latency_ms: number;
    attempts: number;
    degraded: boolean;
    fallback_reason: string | null;
    generated_at: string;
  } | null;
  runs: RunRecord[];
  created_at: string;
  updated_at: string;
  display_title?: string;
}

export interface GenerateResponse {
  result: { workflow: Workflow; provider: string; degraded: boolean; fallback_reason: string | null; latency_ms: number };
  project: Project | null;
  project_id: string | null;
  request_id: string;
}
