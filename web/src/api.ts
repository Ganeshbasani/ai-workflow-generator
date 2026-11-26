import type { GenerateResponse, Project, RunRecord, StepStatus, StepType } from "./types";

const OWNER_KEY = "architect.owner.v1";
const ownerId = (() => {
  const existing = localStorage.getItem(OWNER_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(OWNER_KEY, created);
  return created;
})();

export class ApiError extends Error {
  status: number;
  requestId?: string;
  constructor(message: string, status: number, requestId?: string) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

export type AiStatus = {
  configured: boolean;
  provider: string;
  model: string;
  message: string;
  connected?: boolean;
  generation_ready?: boolean;
  model_available?: boolean;
  available_models?: string[];
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Owner-Id", ownerId);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path.startsWith("/api") ? path : `/api/v1${path}`, {
      ...init,
      headers,
    });
  } catch {
    throw new ApiError(
      "The workflow service could not be reached. Check that the app is running, then try again.",
      0,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: string | { message?: string }; message?: string; detail?: string } | null;
    const nestedMessage = typeof body?.error === "object" ? body.error.message : undefined;
    const fallbackMessage = response.status === 422
      ? path.includes("/workflows/generate")
        ? "We couldn't use that process description. Add a clear action and its object, then try again."
        : "One of those details needs attention. Check your changes and try again."
      : response.status === 429
        ? "Too many requests in a short time. Wait a moment and try again."
        : response.status >= 500
          ? "The workflow service had a problem. Your existing workflows are still saved; please try again."
          : "We couldn't complete that request. Check your changes and try again.";
    const serverMessage = body?.message ?? nestedMessage ?? body?.detail;
    const message = response.status === 422 && (!serverMessage || serverMessage === "Please check your input and try again.")
      ? fallbackMessage
      : serverMessage ?? fallbackMessage;
    throw new ApiError(message, response.status, response.headers.get("X-Request-ID") ?? undefined);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  list: async () => (await request<{ items: Project[] }>("/workflows")).items,
  aiStatus: () => request<AiStatus>("/ai/status"),
  testAi: () => request<AiStatus>("/ai/test", { method: "POST" }),
  get: (id: string) => request<Project>(`/workflows/${id}`),
  generate: (description: string, category: string, additional_context = "", file?: File) => {
    if (file) {
      const body = new FormData();
      body.set("description", description); body.set("category", category);
      body.set("additional_context", additional_context); body.set("session_id", ownerId);
      body.set("file", file);
      return request<GenerateResponse>("/workflows/generate-upload", { method: "POST", body });
    }
    return request<GenerateResponse>("/workflows/generate", {
      method: "POST",
      body: JSON.stringify({ description, category, additional_context, session_id: ownerId, persist: true }),
    });
  },
  rename: (id: string, title: string) => request<Project>(`/workflows/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  replace: (project: Project) => request<Project>(`/workflows/${project.id}`, { method: "PUT", body: JSON.stringify({ workflow: project.workflow }) }),
  addStep: (id: string, title: string, step_type: StepType = "task") => request<Project>(`/workflows/${id}/steps`, { method: "POST", body: JSON.stringify({ title, step_type }) }),
  deleteStep: (id: string, stepId: string) => request<Project>(`/workflows/${id}/steps/${stepId}`, { method: "DELETE" }),
  setStatus: (id: string, stepId: string, status: StepStatus, notes: string) => request<Project>(`/workflows/${id}/runs/steps/${stepId}`, { method: "PATCH", body: JSON.stringify({ status, notes }) }),
  startRun: (id: string) => request<Project>(`/workflows/${id}/runs`, { method: "POST" }),
  finishRun: (id: string, notes = "") => request<Project>(`/workflows/${id}/runs/finish`, { method: "POST", body: JSON.stringify({ outcome: "completed", notes }) }),
  listRuns: (id: string) => request<RunRecord[]>(`/workflows/${id}/runs`),
  remove: (id: string) => request<{ ok: boolean }>(`/workflows/${id}`, { method: "DELETE" }),
  exportUrl: (id: string, format: string) => `/api/v1/workflows/${id}/export?format=${encodeURIComponent(format)}`,
  ownerId,
};
