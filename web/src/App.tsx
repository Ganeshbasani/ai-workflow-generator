import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity, Archive, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight,
  BarChart3, Boxes, Check, CheckCircle2, ChevronDown, CircleHelp,
  ClipboardList, Clock3, Command, Cpu, Download, FileText, GitBranch, GitFork,
  LayoutDashboard, ListOrdered, LoaderCircle, LockKeyhole, Moon, MoreHorizontal, Network,
  PanelLeftClose, Paperclip, Play, Plus, Search, Settings2, ShieldAlert, ShieldCheck,
  Sun, UserRoundPlus, Workflow as WorkflowIcon, X, Zap,
} from "lucide-react";
import {
  applyEdgeChanges, applyNodeChanges, Background, BackgroundVariant,
  Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, ReactFlowProvider,
  type Connection, type Edge, type EdgeChange, type Node, type NodeChange,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api, type AiStatus } from "./api";
import { productAnalyticsConfigured, productAnalyticsEnabled, setProductAnalyticsEnabled, trackProductEvent } from "./analytics";
import type { Project, StepStatus, StepType, Workflow, WorkflowStep } from "./types";

type View = "overview" | "library" | "canvas" | "runs" | "analytics";
type EditorMode = "steps" | "flowchart";
type CanvasNodeData = { step: WorkflowStep; index: number };
type CanvasNode = Node<CanvasNodeData, "workflowStep">;

const CATEGORIES = ["Educational Institutes", "Business Organizations", "Real Estate", "Software Industries", "Software Projects", "Hospitals"];
const TYPES: StepType[] = ["start", "task", "decision", "approval", "notification", "end"];
const STATUSES: StepStatus[] = ["pending", "in_progress", "done", "blocked", "skipped"];
const STARTERS = [
  { icon: <UserRoundPlus size={15} />, title: "Customer onboarding", category: "Software Industries", description: "A new customer signs up, verifies their email, completes a profile, selects a plan, and receives a welcome message. Route accounts that fail verification to support." },
  { icon: <ShieldAlert size={15} />, title: "Incident response", category: "Software Projects", description: "When a production incident is detected, acknowledge it, assess severity, assign an incident lead, notify affected teams, mitigate the issue, verify recovery, and publish a post-incident review. Escalate critical incidents." },
  { icon: <ClipboardList size={15} />, title: "Patient intake", category: "Hospitals", description: "A patient requests an appointment, shares symptoms and medical history, completes insurance verification, and is triaged by a clinician. Escalate urgent cases; schedule routine cases and send preparation instructions." },
];

function workflowOrder(workflow: Workflow): WorkflowStep[] {
  const parents = new Map(workflow.steps.map((step) => [step.id, new Set(step.depends_on)]));
  workflow.steps.forEach((step) => {
    for (const target of [step.on_true, step.on_false]) {
      if (target && parents.has(target)) parents.get(target)!.add(step.id);
    }
  });
  const ready = workflow.steps.filter((step) => parents.get(step.id)?.size === 0);
  const ordered: WorkflowStep[] = [];
  while (ready.length) {
    const step = ready.shift()!;
    ordered.push(step);
    for (const candidate of workflow.steps) {
      const dependencies = parents.get(candidate.id)!;
      if (dependencies.delete(step.id) && dependencies.size === 0) ready.push(candidate);
    }
  }
  return ordered.length === workflow.steps.length ? ordered : workflow.steps;
}

function titleOf(project: Project) { return project.title || project.workflow.title; }
function dateLabel(date: string) { return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(date)); }
function timeLabel(date: string) { return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(date)); }
function elapsedLabel(seconds: number) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`; }
function statusLabel(status: string) { return status.replace("_", " "); }
function countDone(project: Project) { return project.workflow.steps.filter((step) => step.status === "done").length; }

function buildGraph(workflow: Workflow): { nodes: CanvasNode[]; edges: Edge[] } {
  const orderIndex = new Map(workflowOrder(workflow).map((step, index) => [step.id, index]));
  const byId = new Map(workflow.steps.map((step) => [step.id, step]));
  const depth = new Map<string, number>();
  const parents = new Map<string, string[]>();
  workflow.steps.forEach((step) => {
    step.depends_on.forEach((dependency) => parents.set(step.id, [...(parents.get(step.id) ?? []), dependency]));
    if (step.step_type === "decision") {
      for (const target of [step.on_true, step.on_false]) {
        if (target) parents.set(target, [...(parents.get(target) ?? []), step.id]);
      }
    }
  });
  const measure = (id: string, visiting = new Set<string>()): number => {
    if (depth.has(id)) return depth.get(id)!;
    if (visiting.has(id)) return 0;
    const step = byId.get(id);
    if (!step) return 0;
    const next = new Set(visiting).add(id);
    const value = (parents.get(id) ?? []).reduce((max, dep) => Math.max(max, measure(dep, next) + 1), 0);
    depth.set(id, value);
    return value;
  };
  workflow.steps.forEach((step) => measure(step.id));
  const columns = new Map<number, WorkflowStep[]>();
  workflow.steps.forEach((step) => {
    const column = depth.get(step.id) ?? 0;
    columns.set(column, [...(columns.get(column) ?? []), step]);
  });
  const rowById = new Map<string, { row: number; count: number }>();
  columns.forEach((steps) => steps.forEach((step, row) => rowById.set(step.id, { row, count: steps.length })));
  const nodes: CanvasNode[] = workflow.steps.map((step, index) => ({
    id: step.id,
    type: "workflowStep",
    position: {
      x: (((rowById.get(step.id)?.row ?? 0) - ((rowById.get(step.id)?.count ?? 1) - 1) / 2) * 320),
      y: (depth.get(step.id) ?? 0) * 205,
    },
    data: { step, index: orderIndex.get(step.id) ?? index },
    draggable: true,
  }));
  const edges: Edge[] = [];
  workflow.steps.forEach((step) => {
    step.depends_on.forEach((source) => {
      const isDecisionRoute = workflow.steps.some((candidate) => candidate.id === source && candidate.step_type === "decision" && (candidate.on_true === step.id || candidate.on_false === step.id));
      if (byId.has(source) && !isDecisionRoute) edges.push({ id: `${source}-${step.id}`, source, target: step.id, type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed }, animated: false });
    });
    if (step.step_type === "decision") {
      if (step.on_true && byId.has(step.on_true)) {
        const bothOutcomesSame = step.on_true === step.on_false;
        edges.push({ id: `${step.id}-yes-${step.on_true}`, source: step.id, target: step.on_true, type: "smoothstep", label: bothOutcomesSame ? "Yes / No" : "Yes", labelStyle: { fill: "#3b7359", fontWeight: 700, fontSize: 12 }, labelBgStyle: { fill: "#e8f0e8" }, markerEnd: { type: MarkerType.ArrowClosed }, className: "edge-yes" });
      }
      if (step.on_false && byId.has(step.on_false) && step.on_false !== step.on_true) {
        edges.push({ id: `${step.id}-no-${step.on_false}`, source: step.id, target: step.on_false, type: "smoothstep", label: "No", labelStyle: { fill: "#a66b3f", fontWeight: 700, fontSize: 11 }, labelBgStyle: { fill: "#f6eee1" }, markerEnd: { type: MarkerType.ArrowClosed }, className: "edge-no" });
      }
    }
  });
  return { nodes, edges };
}

function wouldCreateCycle(workflow: Workflow, source: string, target: string): boolean {
  const outgoing = new Map<string, string[]>();
  workflow.steps.forEach((step) => {
    step.depends_on.forEach((dependency) => outgoing.set(dependency, [...(outgoing.get(dependency) ?? []), step.id]));
    if (step.on_true) outgoing.set(step.id, [...(outgoing.get(step.id) ?? []), step.on_true]);
    if (step.on_false) outgoing.set(step.id, [...(outgoing.get(step.id) ?? []), step.on_false]);
  });
  const pending = [target]; const visited = new Set<string>();
  while (pending.length) {
    const current = pending.pop()!;
    if (current === source) return true;
    if (visited.has(current)) continue;
    visited.add(current);
    pending.push(...(outgoing.get(current) ?? []));
  }
  return false;
}

function WorkflowStepNode({ data, selected }: NodeProps<CanvasNode>) {
  const { step, index } = data;
  return <div className={`flow-node node-${step.step_type} ${selected ? "selected" : ""}`}>
    <Handle type="target" position={Position.Top} />
    <div className="flow-node-top"><span className="flow-node-index">{String(index + 1).padStart(2, "0")}</span><span className={`node-kind kind-${step.step_type}`}>{step.step_type}</span><span className={`status-dot status-${step.status}`} /></div>
    <div className="flow-node-title">{step.title}</div>
    {step.description && <div className="flow-node-description">{step.description}</div>}
    <div className="flow-node-footer"><span>{step.owner_role || "Unassigned"}</span>{step.estimated_duration && <span>{step.estimated_duration}</span>}</div>
    <Handle type="source" position={Position.Bottom} />
  </div>;
}

const nodeTypes = { workflowStep: WorkflowStepNode };

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [view, setView] = useState<View>("overview");
  const [editorMode, setEditorMode] = useState<EditorMode>("steps");
  const [loading, setLoading] = useState(true);
  const [serviceReady, setServiceReady] = useState(false);
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null);
  const [testingAi, setTestingAi] = useState(false);
  const [showAiGuide, setShowAiGuide] = useState(false);
  const [showAiSettings, setShowAiSettings] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generationStartedAt, setGenerationStartedAt] = useState<number | null>(null);
  const [generationElapsed, setGenerationElapsed] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [dark, setDark] = useState(false);
  const [query, setQuery] = useState("");
  const [commandOpen, setCommandOpen] = useState(false);
  const [selectedStep, setSelectedStep] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState(CATEGORIES[3]);
  const [context, setContext] = useState("");
  const [contextFile, setContextFile] = useState<File | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [runNotes, setRunNotes] = useState("");
  const [canvasNodes, setCanvasNodes] = useState<CanvasNode[]>([]);
  const [canvasEdges, setCanvasEdges] = useState<Edge[]>([]);
  const saveTimer = useRef<number | undefined>(undefined);
  const editRevision = useRef(0);

  useEffect(() => {
    if (!generating || generationStartedAt === null) return;
    const updateElapsed = () => setGenerationElapsed(Math.floor((Date.now() - generationStartedAt) / 1000));
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [generating, generationStartedAt]);

  useEffect(() => {
    api.list().then((items) => { setProjects(items); setServiceReady(true); }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Couldn't reach the workflow service.")).finally(() => setLoading(false));
    api.aiStatus().then(setAiStatus).catch(() => setAiStatus(null));
  }, []);

  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen((open) => !open); }
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        const form = document.getElementById("workflow-brief")?.closest("form");
        if (form instanceof HTMLFormElement) { event.preventDefault(); form.requestSubmit(); }
      }
      if (event.key === "Escape") { setCommandOpen(false); setSearchOpen(false); setMobileNav(false); }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const allRuns = useMemo(() => projects.flatMap((project) => project.runs.map((run) => ({ ...run, projectTitle: titleOf(project), projectId: project.id }))).sort((a, b) => b.started_at.localeCompare(a.started_at)), [projects]);
  const filteredProjects = useMemo(() => projects.filter((project) => `${titleOf(project)} ${project.workflow.domain} ${project.metadata?.category ?? ""}`.toLowerCase().includes(query.toLowerCase())), [projects, query]);
  const activeWorkflow = activeProject?.workflow;
  const graph = useMemo(() => activeWorkflow ? buildGraph(activeWorkflow) : { nodes: [], edges: [] }, [activeWorkflow]);
  const selected = activeWorkflow?.steps.find((step) => step.id === selectedStep) ?? null;

  useEffect(() => {
    let positions: Record<string, { x: number; y: number }> = {};
    if (activeProject?.id) {
      try { positions = JSON.parse(localStorage.getItem(`architect.layout.v2.${activeProject.id}`) ?? "{}"); } catch { positions = {}; }
    }
    setCanvasNodes((previous) => graph.nodes.map((node) => {
      const old = previous.find((item) => item.id === node.id);
      return { ...node, position: positions[node.id] ?? old?.position ?? node.position };
    }));
    setCanvasEdges(graph.edges);
  }, [graph, activeProject?.id]);

  const notify = (message: string) => { setToast(message); setError(""); };
  const openProject = (project: Project) => { setActiveProject(project); setSelectedStep(project.workflow.steps[0]?.id ?? null); setEditorMode("steps"); setView("canvas"); setError(""); };
  const saveWorkflow = async (next: Workflow) => {
    if (!activeProject) return;
    const payload = { ...activeProject, workflow: next };
    setActiveProject(payload);
    setSaving(true);
    try {
      const saved = await api.replace(payload);
      setActiveProject(saved);
      setProjects((items) => items.map((item) => item.id === saved.id ? saved : item));
      trackProductEvent("workflow_edited");
      notify("All changes saved");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn't save this workflow.");
    } finally { setSaving(false); }
  };

  const updateStep = (stepId: string, patch: Partial<WorkflowStep>) => {
    if (!activeProject) return;
    if (patch.status) {
      const step = activeProject.workflow.steps.find((item) => item.id === stepId);
      void api.setStatus(activeProject.id, stepId, patch.status, step?.notes ?? "").then((project) => {
        setActiveProject(project);
        setProjects((items) => items.map((item) => item.id === project.id ? project : item));
        notify("Progress saved to the run history");
      }).catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Couldn't update progress."));
      return;
    }
    const nextProject = { ...activeProject, workflow: { ...activeProject.workflow, steps: activeProject.workflow.steps.map((step) => step.id === stepId ? { ...step, ...patch } : step) } };
    setActiveProject(nextProject);
    setProjects((items) => items.map((item) => item.id === nextProject.id ? nextProject : item));
    setSaving(true);
    editRevision.current += 1;
    const revision = editRevision.current;
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      void api.replace(nextProject).then((saved) => {
        if (revision === editRevision.current) {
          setActiveProject(saved);
          setProjects((items) => items.map((item) => item.id === saved.id ? saved : item));
          setSaving(false);
          notify("All changes saved");
        }
      }).catch((cause: unknown) => {
        if (revision === editRevision.current) { setSaving(false); setError(cause instanceof Error ? cause.message : "Couldn't save this workflow."); }
      });
    }, 550);
  };

  const generate = async (event: FormEvent) => {
    event.preventDefault();
    if (!description.trim() && !contextFile) { setError("Describe the process or attach a document to analyze."); return; }
    if (contextFile && !aiStatus?.configured) { setError("Document analysis needs a connected AI model. Connect Ollama or an API provider before uploading a document."); return; }
    trackProductEvent("workflow_generation_started", { input_type: contextFile ? "document" : "description" });
    setGenerating(true); setError(""); setGenerationElapsed(0); setGenerationStartedAt(Date.now());
    try {
      const response = await api.generate(description, category, context, contextFile ?? undefined);
      if (!response.project) throw new Error("The workflow was created but not saved. Try again.");
      trackProductEvent("workflow_generation_completed", { provider: response.result.provider, step_count: response.project.workflow.steps.length });
      setActiveProject(response.project);
      setProjects((items) => [response.project!, ...items.filter((item) => item.id !== response.project!.id)]);
      setSelectedStep(response.project.workflow.steps[0]?.id ?? null); setEditorMode("steps");
      setDescription(""); setContext(""); setContextFile(null); setView("canvas");
      notify(response.result.provider === "rule" ? "Source-based draft created. Review the steps and branches." : "AI workflow created and ready to review.");
    } catch (cause) { trackProductEvent("workflow_generation_failed"); setError(cause instanceof Error ? cause.message : "Workflow generation failed."); }
    finally { setGenerating(false); setGenerationStartedAt(null); }
  };

  const testAiConnection = async () => {
    setTestingAi(true);
    try {
      const status = await api.testAi();
      setAiStatus(status);
      if (status.connected) notify(status.message);
      else setError(status.message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The AI connection could not be tested.");
    } finally {
      setTestingAi(false);
    }
  };

  const addStep = async () => {
    if (!activeProject) return;
    try {
      const project = await api.addStep(activeProject.id, "New workflow step");
      setActiveProject(project); setProjects((items) => items.map((item) => item.id === project.id ? project : item));
      const added = project.workflow.steps.at(-1);
      if (added) setSelectedStep(added.id);
      notify("Step added to your workflow");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't add a step."); }
  };

  const deleteStep = async (stepId: string) => {
    if (!activeProject) return;
    try {
      const project = await api.deleteStep(activeProject.id, stepId);
      setActiveProject(project); setProjects((items) => items.map((item) => item.id === project.id ? project : item));
      setSelectedStep(project.workflow.steps[0]?.id ?? null); notify("Step removed");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't remove this step."); }
  };

  const connectSteps = async (connection: Connection) => {
    if (!activeWorkflow || !connection.source || !connection.target || connection.source === connection.target) return;
    if (wouldCreateCycle(activeWorkflow, connection.source, connection.target)) { setError("That connection would create a cycle. Choose a later step instead."); return; }
    const target = activeWorkflow.steps.find((step) => step.id === connection.target);
    if (!target || target.depends_on.includes(connection.source)) return;
    const next = { ...activeWorkflow, steps: activeWorkflow.steps.map((step) => step.id === target.id ? { ...step, depends_on: [...step.depends_on, connection.source!] } : step) };
    await saveWorkflow(next);
  };

  const onNodesChange = (changes: NodeChange<CanvasNode>[]) => {
    const removed = changes.filter((change) => change.type === "remove").map((change) => change.id);
    if (removed.length) { void (async () => { for (const id of removed) await deleteStep(id); })(); return; }
    setCanvasNodes((nodes) => {
      const next = applyNodeChanges(changes, nodes);
      if (activeProject) localStorage.setItem(`architect.layout.v2.${activeProject.id}`, JSON.stringify(Object.fromEntries(next.map((node) => [node.id, node.position]))));
      return next;
    });
  };
  const onEdgesChange = (changes: EdgeChange<Edge>[]) => {
    setCanvasEdges((edges) => applyEdgeChanges(changes, edges));
    if (!activeWorkflow) return;
    const removed = changes.filter((change) => change.type === "remove").map((change) => change.id);
    if (!removed.length) return;
    const removedEdges = graph.edges.filter((edge) => removed.includes(edge.id));
    const next = { ...activeWorkflow, steps: activeWorkflow.steps.map((step) => {
      const removedIncoming = removedEdges.filter((edge) => edge.target === step.id && !edge.id.includes("-yes-") && !edge.id.includes("-no-"));
      return { ...step,
        depends_on: step.depends_on.filter((source) => !removedIncoming.some((edge) => edge.source === source)),
        on_true: removedEdges.some((edge) => edge.source === step.id && edge.id.includes("-yes-")) ? null : step.on_true,
        on_false: removedEdges.some((edge) => edge.source === step.id && edge.id.includes("-no-")) ? null : step.on_false,
      };
    }) };
    void saveWorkflow(next);
  };

  const renameProject = async (title: string) => {
    if (!activeProject || !title.trim() || titleOf(activeProject) === title.trim()) return;
    try { const project = await api.rename(activeProject.id, title.trim()); setActiveProject(project); setProjects((items) => items.map((item) => item.id === project.id ? project : item)); notify("Workflow renamed"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't rename workflow."); }
  };

  const removeProject = async (project: Project) => {
    if (!window.confirm(`Delete “${titleOf(project)}”? This also removes its run history.`)) return;
    try { await api.remove(project.id); setProjects((items) => items.filter((item) => item.id !== project.id)); if (activeProject?.id === project.id) { setActiveProject(null); setView("overview"); } notify("Workflow deleted"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't delete workflow."); }
  };

  const downloadExport = async (format: string) => {
    if (!activeProject) return;
    try {
      const response = await fetch(api.exportUrl(activeProject.id, format), { headers: { "X-Owner-Id": api.ownerId } });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { message?: string } | null;
        throw new Error(body?.message ?? `The ${format.replaceAll("_", " ")} export could not be created.`);
      }
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const suggestedName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
      link.href = url; link.download = suggestedName || `${titleOf(activeProject).toLowerCase().replace(/[^a-z0-9]+/g, "-")}.${format}`;
      document.body.append(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); trackProductEvent("workflow_exported", { format }); notify(`${format.replaceAll("_", " ").toUpperCase()} export downloaded`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Export failed."); }
  };

  const startRun = async () => {
    if (!activeProject) return;
    try { const project = await api.startRun(activeProject.id); setActiveProject(project); setProjects((items) => items.map((item) => item.id === project.id ? project : item)); trackProductEvent("workflow_run_started"); setView("runs"); notify("Run started"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't start a run."); }
  };

  const updateRunStep = async (step: WorkflowStep, status: StepStatus, notes: string) => {
    if (!activeProject) return;
    try { const project = await api.setStatus(activeProject.id, step.id, status, notes); setActiveProject(project); setProjects((items) => items.map((item) => item.id === project.id ? project : item)); notify("Progress updated"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't update progress."); }
  };

  const finishRun = async () => {
    if (!activeProject) return;
    try { const project = await api.finishRun(activeProject.id, runNotes); setActiveProject(project); setProjects((items) => items.map((item) => item.id === project.id ? project : item)); setRunNotes(""); notify("Run completed and saved"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't complete the run."); }
  };

  const nav = (next: View) => { setView(next); setMobileNav(false); setError(""); };

  return <div className={`app-shell ${dark ? "dark" : ""}`}>
    <aside className={`sidebar ${mobileNav ? "mobile-open" : ""}`}>
      <div className="brand-row"><div className="brand-mark" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none"><path d="M8.5 20h8.2m0 0h5.1m0 0 8.7-9m-8.7 9 8.7 9" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round"/><circle cx="8.5" cy="20" r="2.7" fill="currentColor"/><path d="m21.8 15.6 4.4 4.4-4.4 4.4-4.4-4.4z" fill="var(--clay)" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/><circle cx="31" cy="11" r="2.5" fill="currentColor"/><circle cx="31" cy="29" r="2.5" fill="currentColor"/></svg></div><div><strong>Architect</strong><span>WORKFLOW STUDIO</span></div><button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={17} /></button></div>
      <div className="workspace-switch"><div className="workspace-avatar">A</div><div className="workspace-name"><strong>My workspace</strong><span>Personal space</span></div></div>
      <button className="new-workflow-button" onClick={() => { nav("overview"); window.setTimeout(() => document.getElementById("workflow-brief")?.focus(), 0); }}><Plus size={16} /> New workflow <ArrowRight size={15} /></button>
      <section className="sidebar-section" aria-label="Dashboard">
        <div className="side-label">Dashboard</div>
        <nav className="side-nav" aria-label="Dashboard navigation">
          <NavButton icon={<LayoutDashboard size={17} />} label="Dashboard" active={view === "overview"} onClick={() => nav("overview")} />
          <NavButton icon={<BarChart3 size={17} />} label="Analytics" active={view === "analytics"} onClick={() => nav("analytics")} />
        </nav>
      </section>
      <section className="sidebar-section" aria-label="Workflow">
        <div className="side-label">Workflow</div>
        <nav className="side-nav" aria-label="Workflow navigation">
          <NavButton icon={<Boxes size={17} />} label="Workflows" active={view === "library"} count={projects.length} onClick={() => nav("library")} />
          <NavButton icon={<Activity size={17} />} label="Runs" active={view === "runs"} count={allRuns.length || undefined} onClick={() => nav("runs")} />
        </nav>
      </section>
      <section className="sidebar-section sidebar-recent" aria-label="Recent workflows">
        <div className="side-project-heading"><span className="side-label">Recent workflows</span><button className="icon-button tiny" onClick={() => nav("library")} aria-label="Browse workflows"><ArrowRight size={14} /></button></div>
        <div className="side-projects">{projects.slice(0, 6).map((project) => <button key={project.id} className={`side-project ${activeProject?.id === project.id ? "active" : ""}`} onClick={() => openProject(project)}><span className="project-spark">{project.workflow.steps.length > 7 ? <GitBranch size={14} /> : <WorkflowIcon size={14} />}</span><span>{titleOf(project)}</span></button>)}{!projects.length && !loading && <p className="side-empty">Your next process starts here.</p>}</div>
      </section>
      <div className="sidebar-spacer" />
      <div className="side-footer"><div className={`connection-status ${!serviceReady && !loading ? "connection-offline" : ""}`}><span />{loading ? "Connecting to workspace" : serviceReady ? "Workspace connected" : "Connection unavailable"}</div><div className="profile-button"><div className="profile-avatar">G</div><span><strong>Guest workspace</strong><small>Local account</small></span></div></div>
    </aside>

    {mobileNav && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <main className="main-shell">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open menu"><PanelLeftClose size={18} /></button><span className="breadcrumb-muted">Workspace</span><span className="crumb-slash">/</span><span>{view === "canvas" && activeProject ? titleOf(activeProject) : ({ overview: "Dashboard", library: "Workflows", runs: "Runs", analytics: "Analytics" } as Record<View, string>)[view]}</span></div>
        <div className="topbar-actions"><button className="search-trigger" onClick={() => setSearchOpen(true)}><Search size={15} /><span>Search anything…</span><kbd>⌘ K</kbd></button><span className="topbar-divider" /><button className="icon-button" onClick={() => setDark((value) => !value)} aria-label="Toggle appearance">{dark ? <Sun size={17} /> : <Moon size={17} />}</button><button className="topbar-avatar settings-avatar" title="AI provider settings" aria-label="AI provider settings" onClick={() => setShowAiSettings(true)}>G</button></div>
      </header>

      {error && <div className="global-error" role="alert"><CircleHelp size={16} /><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss"><X size={16} /></button></div>}
      {loading ? <div className="loading-screen"><LoaderCircle size={28} className="spin" /><span>Opening your workspace…</span></div> : <>
        {view === "overview" && <Overview projects={projects} onOpen={openProject} description={description} setDescription={setDescription} category={category} setCategory={setCategory} context={context} setContext={setContext} contextFile={contextFile} setContextFile={setContextFile} onGenerate={generate} generating={generating} generationElapsed={generationElapsed} aiStatus={aiStatus} onTemplate={(starter) => { trackProductEvent("workflow_template_used", { category: starter.category }); setCategory(starter.category); setDescription(starter.description); document.getElementById("workflow-brief")?.focus(); }} onLibrary={() => nav("library")} />}
        {view === "library" && <Library projects={filteredProjects} query={query} setQuery={setQuery} onOpen={openProject} onDelete={removeProject} onCreate={() => nav("overview")} />}
        {view === "canvas" && activeProject && <div className="canvas-page">
          <section className="canvas-toolbar"><div><button className="back-button" onClick={() => nav("library")}><ArrowLeft size={15} /> Workflows</button><div className="canvas-title-row"><input className="canvas-title-input" key={activeProject.id} defaultValue={titleOf(activeProject)} onBlur={(event) => void renameProject(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }} /><span className="workflow-domain-pill">{activeProject.workflow.domain || activeProject.metadata?.category}</span></div><div className="canvas-subtitle">{activeProject.workflow.summary || "Review and refine this workflow"} <span>·</span> {activeProject.workflow.steps.length} steps</div></div><div className="canvas-actions"><span className={`generation-source ${activeProject.metadata?.provider === "rule" ? "source-rule" : "source-ai"}`}>{!activeProject.metadata ? "Existing workflow" : activeProject.metadata.provider === "rule" ? "Rule-based draft" : `AI · ${activeProject.metadata.model || "model"}`}</span><span className={`save-indicator ${saving ? "saving" : ""}`}>{saving ? <LoaderCircle size={13} className="spin" /> : <Check size={13} />}{saving ? "Saving" : "Saved"}</span><ExportMenu onExport={downloadExport} /><button className="button button-primary" onClick={() => void startRun()}><Play size={15} fill="currentColor" /> Run workflow</button></div></section>
          {(activeProject.metadata?.degraded || activeProject.metadata?.provider === "rule") && <div className="notice-warning"><Zap size={16} /><span>{activeProject.metadata?.degraded ? <>AI generation failed, so this is a rule-based draft. {activeProject.metadata.fallback_reason || "Review every step before using it."} Check the draft carefully before using it.</> : "This workflow was generated without a language model. Check the wording and add any missing steps before using it."}</span></div>}
          <div className="canvas-layout"><section className="flow-surface"><div className="flow-topbar"><div className="editor-mode-tabs" role="tablist" aria-label="Workflow view"><button role="tab" aria-selected={editorMode === "steps"} className={`editor-mode-tab ${editorMode === "steps" ? "active" : ""}`} onClick={() => setEditorMode("steps")}><ListOrdered size={16} /> Steps <b>{activeProject.workflow.steps.length}</b></button><button role="tab" aria-selected={editorMode === "flowchart"} className={`editor-mode-tab ${editorMode === "flowchart" ? "active" : ""}`} onClick={() => setEditorMode("flowchart")}><Network size={15} /> Flowchart</button></div><div className="flow-tools"><button className="tool-button" onClick={() => void addStep()}><Plus size={14} /> Add step</button><span className="tool-divider" /><span className="canvas-hint">{editorMode === "steps" ? "Select a step to edit its details" : "Drag a handle to connect; drag the canvas to pan"}</span></div></div>
            {editorMode === "steps" ? <StepSequence steps={workflowOrder(activeProject.workflow)} selectedId={selectedStep} onSelect={setSelectedStep} /> : <div className="flow-canvas"><ReactFlow<CanvasNode, Edge> nodes={canvasNodes} edges={canvasEdges} nodeTypes={nodeTypes} onNodeClick={(_, node) => setSelectedStep(node.id)} onPaneClick={() => setSelectedStep(null)} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={(connection) => void connectSteps(connection)} isValidConnection={(connection) => !!activeWorkflow && !wouldCreateCycle(activeWorkflow, connection.source, connection.target)} fitView fitViewOptions={{ padding: 0.2 }} minZoom={0.68} maxZoom={1.15} deleteKeyCode={["Backspace", "Delete"]} defaultEdgeOptions={{ type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: dark ? "#91b5a1" : "#64816f", strokeWidth: 2.2 } }} proOptions={{ hideAttribution: true }}><Background variant={BackgroundVariant.Dots} gap={20} size={1} color={dark ? "#394b42" : "#dce5de"} /><Controls position="bottom-left" showInteractive={false} /><MiniMap position="bottom-right" pannable zoomable nodeColor={() => dark ? "#4e8a6b" : "#438267"} maskColor={dark ? "rgba(15, 20, 32, .7)" : "rgba(248, 249, 251, .65)"} /></ReactFlow></div>}
            <div className="flow-statusbar"><span><span className="status-dot status-done" /> {countDone(activeProject)} completed</span><span><span className="status-dot status-pending" /> {activeProject.workflow.steps.filter((step) => step.status === "pending").length} pending</span><span className="flow-save-label">Graph validation active</span></div>
          </section>
          <aside className="inspector-panel">{selected ? <StepInspector step={selected} workflow={activeProject.workflow} onChange={(patch) => updateStep(selected.id, patch)} onDelete={() => void deleteStep(selected.id)} /> : <><div className="inspector-empty-icon"><Settings2 size={19} /></div><h3>Workflow details</h3><p>Select any node to edit its steps, owner, duration, and decision paths.</p><div className="review-block"><div className="review-title"><ShieldCheck size={15} /> Quality review</div><QualityReview workflow={activeProject.workflow} /></div><div className="review-block"><div className="review-title"><CircleHelp size={15} /> AI notes</div>{activeProject.workflow.assumptions.slice(0, 2).map((item, index) => <p className="insight-line" key={index}>{item}</p>)}{!activeProject.workflow.assumptions.length && <p className="insight-line">No assumptions were recorded.</p>}</div></>}</aside></div>
        </div>}
        {view === "runs" && <Runs projects={projects} activeProject={activeProject} setActiveProject={setActiveProject} allRuns={allRuns} onOpen={openProject} onStart={startRun} onUpdate={updateRunStep} onFinish={finishRun} notes={runNotes} setNotes={setRunNotes} />}
        {view === "analytics" && <Analytics projects={projects} runs={allRuns} />}
      </>}
    </main>
    {searchOpen && <CommandDialog projects={projects} onClose={() => setSearchOpen(false)} onNavigate={nav} onOpen={(project) => { setSearchOpen(false); openProject(project); }} />}
    {commandOpen && <CommandDialog projects={projects} onClose={() => setCommandOpen(false)} onNavigate={(next) => { setCommandOpen(false); nav(next); }} onOpen={(project) => { setCommandOpen(false); openProject(project); }} />}
    {showAiSettings && <div className="dialog-backdrop settings-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowAiSettings(false); }}><section className="settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-dialog-title"><div className="settings-dialog-heading"><div><div className="eyebrow">WORKSPACE SETTINGS</div><h2 id="settings-dialog-title">AI provider</h2><p>Connection status and local setup guidance.</p></div><button className="icon-button" aria-label="Close AI provider settings" onClick={() => setShowAiSettings(false)}><X size={17} /></button></div><AiConnectionCard status={aiStatus} testing={testingAi} onTest={testAiConnection} showGuide={showAiGuide} setShowGuide={setShowAiGuide} /><AnalyticsSettings /></section></div>}
    {toast && <div className="toast"><CheckCircle2 size={17} /> {toast}</div>}
  </div>;
}

function NavButton({ icon, label, active, count, onClick }: { icon: ReactNode; label: string; active: boolean; count?: number; onClick: () => void }) {
  return <button className={`side-nav-item ${active ? "active" : ""}`} onClick={onClick}>{icon}<span>{label}</span>{count !== undefined && <small>{count}</small>}</button>;
}

function AiConnectionCard({ status, testing, onTest, showGuide, setShowGuide }: { status: AiStatus | null; testing: boolean; onTest: () => void; showGuide: boolean; setShowGuide: (value: boolean) => void }) {
  const configured = status?.configured ?? false;
  const connected = status?.connected;
  const className = connected === false ? "ai-connection-card ai-disconnected" : configured ? "ai-connection-card ai-configured" : "ai-connection-card ai-unconfigured";
  return <section className={className}>
    <div className="ai-connection-icon"><Cpu size={18} /></div>
    <div className="ai-connection-copy">
      <div className="ai-connection-heading"><strong>{configured ? "AI provider" : "Connect Ollama for AI-powered workflows"}</strong><span className="ai-connection-status">{status?.generation_ready === true || (status?.generation_ready === undefined && status?.connected === true) ? "Ready for generation" : status?.connected === false ? "Needs attention" : configured ? "Configured · not tested" : "Offline draft mode"}</span></div>
      <p>{status?.message ?? "Checking the AI provider configuration…"}</p>
      {showGuide && <div className="ai-setup-guide"><p><strong>Ollama on Windows + Docker Desktop</strong></p><ol><li>Quit Ollama from the system tray.</li><li>In Windows, set the user environment variable <code>OLLAMA_HOST</code> to <code>0.0.0.0:11434</code>, then reopen Ollama. Use a private network and firewall rules; do not expose this port to the public internet.</li><li>In the project <code>.env</code>, use the exact installed model from <code>ollama list</code>:</li></ol><pre>{"LLM_PROVIDER=ollama\nLLM_BASE_URL=http://host.docker.internal:11434/v1\nLLM_MODEL=qwen3.5:4b"}</pre><p>From the project folder, run <code>docker compose up -d --build --force-recreate</code>, then test the connection again. If you run the app directly on Windows instead of Docker, use <code>http://localhost:11434/v1</code>.</p></div>}
      {testing && <p className="ai-test-note">A cold local model can take a minute or two to answer its first request.</p>}
      {status?.available_models?.length ? <p className="ai-model-list"><strong>Available models:</strong> {status.available_models.join(", ")}</p> : null}
    </div>
    <div className="ai-connection-actions">
      {configured && <button className="button button-quiet" disabled={testing} onClick={onTest}>{testing ? <LoaderCircle size={15} className="spin" /> : <Activity size={15} />}{testing ? "Testing…" : "Test connection"}</button>}<button className="button button-quiet" onClick={() => setShowGuide(!showGuide)}>{showGuide ? "Hide setup" : configured ? "Connection setup" : "Setup Ollama"}<ArrowRight size={14} /></button>
    </div>
  </section>;
}

function AnalyticsSettings() {
  const available = productAnalyticsConfigured();
  const [enabled, setEnabled] = useState(productAnalyticsEnabled());
  return <section className="analytics-settings"><div><strong>Optional product analytics</strong><p>{available ? "Share basic feature usage to help improve Architect. Workflow text, uploaded documents, and step details are never included." : "Analytics are off on localhost and until a PostHog project key is configured."}</p></div>{available && <label className="analytics-consent-control"><input type="checkbox" checked={enabled} onChange={(event) => { const next = event.target.checked; if (setProductAnalyticsEnabled(next)) setEnabled(next); }} /><span>Allow anonymous usage events</span></label>}</section>;
}

function Overview(props: { projects: Project[]; onOpen: (project: Project) => void; description: string; setDescription: (value: string) => void; category: string; setCategory: (value: string) => void; context: string; setContext: (value: string) => void; contextFile: File | null; setContextFile: (value: File | null) => void; onGenerate: (event: FormEvent) => void; generating: boolean; generationElapsed: number; aiStatus: AiStatus | null; onTemplate: (starter: typeof STARTERS[number]) => void; onLibrary: () => void }) {
  const { projects, onOpen, description, setDescription, category, setCategory, context, setContext, contextFile, setContextFile, onGenerate, generating, generationElapsed, aiStatus, onTemplate, onLibrary } = props;
  const runs = projects.reduce((sum, project) => sum + project.runs.length, 0);
  const done = projects.reduce((sum, project) => sum + project.workflow.steps.filter((step) => step.status === "done").length, 0);
  return <div className="page-content overview-page"><div className="page-heading"><div><div className="eyebrow">WORKFLOW BUILDER</div><h1>Turn a real process into a clear workflow.</h1><p>Write what people do, where decisions happen, and how the work ends. Review the steps, then open the flowchart.</p></div><div className="heading-badge"><span className="live-pulse" /> Workspace ready</div></div>
    {projects.length > 0 && <div className="stat-grid"><StatCard icon={<WorkflowIcon size={17} />} label="Workflows" value={projects.length} meta="Saved in your workspace" tint="violet" /><StatCard icon={<Play size={16} />} label="Runs recorded" value={runs} meta="Execution history" tint="blue" /><StatCard icon={<CheckCircle2 size={17} />} label="Steps completed" value={done} meta="Across all workflows" tint="green" /><StatCard icon={<Download size={16} />} label="Export formats" value="7" meta="PDF, JSON, CSV & more" tint="amber" /></div>}
    <div className="overview-grid"><section className="creation-card"><div className="creation-intro"><div><div className="eyebrow">BUILD A WORKFLOW</div><h2>Describe the process in your team's words.</h2><p>Include the trigger, each action, decision outcomes, and the final result. Steps and flowchart are generated together.</p></div><div className="creation-spark"><GitBranch size={22} /></div></div><form onSubmit={onGenerate}><label className="field-label" htmlFor="workflow-brief">Process description{contextFile ? " · optional with a document" : ""}</label><textarea id="workflow-brief" value={description} onChange={(event) => setDescription(event.target.value)} placeholder={contextFile ? "Optional guidance: tell the AI which process or section to focus on." : "Example: When a customer requests a refund, support checks the order and eligibility. If eligible, approve and issue the refund; otherwise explain the reason. Then notify the customer and record the outcome."} rows={5} maxLength={4000} /><div className="brief-footer"><label className="field-label" htmlFor="workflow-category">Team or industry</label><select id="workflow-category" value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map((item) => <option key={item}>{item}</option>)}</select><span className="char-count">{description.length.toLocaleString()} / 4,000</span></div><label className="file-attachment">{contextFile ? <FileText size={14} /> : <Paperclip size={14} />}<span>{contextFile ? contextFile.name : "Attach a PDF or text file"}</span><small>{contextFile ? `${(contextFile.size / 1024).toFixed(0)} KB` : "Up to 5 MB"}</small><input type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={(event) => setContextFile(event.target.files?.[0] ?? null)} />{contextFile && <button type="button" className="remove-file" aria-label="Remove attachment" onClick={(event) => { event.preventDefault(); setContextFile(null); }}><X size={13} /></button>}</label>{contextFile && <p className="document-ai-note">{aiStatus?.configured ? "The uploaded document will be analyzed by the connected AI model." : "Connect Ollama or an API provider to analyze an uploaded document. Offline rules do not analyze document content."}</p>}<details className="context-accordion"><summary><FileText size={14} /> Add internal context <span>Policies, roles, or constraints</span></summary><textarea value={context} onChange={(event) => setContext(event.target.value)} placeholder="Paste relevant policy text or supporting process details…" rows={3} maxLength={20000} /></details><div className="creation-actions"><button className="button button-primary button-create" disabled={generating || (!description.trim() && !contextFile) || (!!contextFile && !aiStatus?.configured)}><span>{generating ? <LoaderCircle size={16} className="spin" /> : <GitBranch size={16} />}{generating ? `${contextFile ? "Analyzing document" : "Generating workflow"} · ${elapsedLabel(generationElapsed)}` : contextFile ? aiStatus?.configured ? "Analyze document with AI" : "Connect AI to analyze document" : aiStatus?.configured ? "Generate with AI" : "Create offline draft"}</span><kbd>⌘ ↵</kbd></button><span className="privacy-note"><LockKeyhole size={13} /> Saved in this workspace</span></div>{aiStatus?.provider.toLowerCase().includes("ollama") && aiStatus.configured && <p className="local-model-note">Local Ollama generation can take up to 4 minutes on this machine. Document analysis requires a successful AI response; it never silently falls back to rules.</p>}</form></section>
      <aside className="starter-panel"><div className="starter-heading"><div><div className="eyebrow">A GOOD PLACE TO START</div><h3>Starter briefs</h3></div><span className="starter-count">03</span></div><p>Choose a common process, then shape it for your team.</p><div className="starter-list">{STARTERS.map((starter) => <button className="starter-item" key={starter.title} onClick={() => onTemplate(starter)}><span className="starter-icon">{starter.icon}</span><span className="starter-copy"><strong>{starter.title}</strong><small>{starter.category}</small></span><ArrowUpRight size={15} /></button>)}</div><div className="starter-footer"><ShieldCheck size={14} /> Every draft is checked for missing paths and assumptions.</div></aside></div>
    <section className="recent-section"><div className="section-heading"><div><div className="eyebrow">PICK UP WHERE YOU LEFT OFF</div><h2>Recent workflows</h2></div><button className="text-button" onClick={onLibrary}>Browse all <ArrowRight size={14} /></button></div>{projects.length ? <div className="recent-grid">{projects.slice(0, 3).map((project) => <ProjectCard project={project} key={project.id} onClick={() => onOpen(project)} compact />)}</div> : <div className="empty-card"><div className="empty-illustration"><WorkflowIcon size={22} /></div><div><strong>Your workflow library is ready.</strong><p>Create your first blueprint and it will show up here.</p></div></div>}</section>
  </div>;
}

function StepSequence({ steps, selectedId, onSelect }: { steps: WorkflowStep[]; selectedId: string | null; onSelect: (stepId: string) => void }) {
  const names = new Map(steps.map((step) => [step.id, step.title]));
  if (!steps.length) return <div className="step-sequence-empty"><div className="empty-illustration"><ListOrdered size={20} /></div><h3>No steps yet</h3><p>Add a step to begin building the process.</p></div>;
  return <ol className="step-sequence" aria-label="Ordered workflow steps">{steps.map((step, index) => <li className="step-sequence-item" key={step.id}>
    <span className={`sequence-index sequence-${step.step_type}`}>{String(index + 1).padStart(2, "0")}</span>
    <button className={`sequence-card ${selectedId === step.id ? "selected" : ""}`} aria-pressed={selectedId === step.id} onClick={() => onSelect(step.id)}>
      <div className="sequence-card-heading"><strong>{step.title}</strong><span className={`sequence-status status-${step.status}`}>{statusLabel(step.status)}</span></div>
      {step.description && <p>{step.description}</p>}
      {step.step_type === "decision" && <div className="sequence-branches"><span>{step.condition || "Decision condition not defined"}</span><span className="branch-yes">Yes → {step.on_true ? names.get(step.on_true) || "Linked step" : "Not set"}</span><span className="branch-no">No → {step.on_false ? names.get(step.on_false) || "Linked step" : "Not set"}</span></div>}
      <div className="sequence-meta"><span className={`sequence-type type-${step.step_type}`}>{step.step_type.replace("_", " ")}</span>{step.owner_role && <span>{step.owner_role}</span>}{step.estimated_duration && <span>{step.estimated_duration}</span>}{step.depends_on.length > 0 && <span>After {step.depends_on.map((id) => names.get(id) || id).join(", ")}</span>}</div>
      <span className="sequence-edit">Edit details <ArrowRight size={13} /></span>
    </button>
  </li>)}</ol>;
}

function StatCard({ icon, label, value, meta, tint }: { icon: ReactNode; label: string; value: string | number; meta: string; tint: string }) {
  return <div className="stat-card"><div className={`stat-icon ${tint}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-meta">{meta}</div></div>;
}

function ProjectCard({ project, onClick, onDelete, compact = false }: { project: Project; onClick: () => void; onDelete?: () => void; compact?: boolean }) {
  const completed = countDone(project); const total = project.workflow.steps.length; const percent = total ? Math.round((completed / total) * 100) : 0;
  return <article className={`project-card ${compact ? "compact" : ""}`}><button className="project-card-main" onClick={onClick}><div className="project-card-icon"><WorkflowIcon size={17} /></div><div className="project-card-content"><div className="project-card-title-row"><strong>{titleOf(project)}</strong><ArrowUpRight size={14} /></div><p>{project.workflow.summary || (total ? "Workflow blueprint" : "This saved workflow has no steps yet. Open it to repair the draft.")}</p><div className="project-card-meta"><span className="domain-chip">{project.workflow.domain || project.metadata?.category || "General"}</span>{total === 0 && <span className="workflow-warning-chip">Needs steps</span>}<span>{total} steps</span><span>Updated {dateLabel(project.updated_at)}</span></div><div className="progress-track"><span style={{ width: `${percent}%` }} /></div></div></button>{onDelete && <button className="project-delete" onClick={onDelete} title="Delete workflow"><MoreHorizontal size={16} /></button>}</article>;
}

function Library({ projects, query, setQuery, onOpen, onDelete, onCreate }: { projects: Project[]; query: string; setQuery: (query: string) => void; onOpen: (project: Project) => void; onDelete: (project: Project) => void; onCreate: () => void }) {
  return <div className="page-content library-page"><div className="page-heading"><div><div className="eyebrow">YOUR WORKSPACE</div><h1>Workflow library</h1><p>Every process your team has mapped, ready to refine and put into practice.</p></div><button className="button button-primary" onClick={onCreate}><Plus size={16} /> New workflow</button></div><div className="library-toolbar"><div className="library-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name, domain, or team…" /><kbd>⌘ F</kbd></div><span className="result-count">{projects.length} {projects.length === 1 ? "workflow" : "workflows"}</span></div>{projects.length ? <div className="library-grid">{projects.map((project) => <ProjectCard project={project} key={project.id} onClick={() => onOpen(project)} onDelete={() => onDelete(project)} />)}</div> : <div className="empty-large"><div className="empty-illustration"><Archive size={22} /></div><h3>{query ? "No matching workflows" : "Your library is empty"}</h3><p>{query ? "Try a different name or team." : "Create a first workflow and it will be saved here automatically."}</p>{!query && <button className="button button-primary" onClick={onCreate}><Plus size={15} /> Create a workflow</button>}</div>}</div>;
}

function StepInspector({ step, workflow, onChange, onDelete }: { step: WorkflowStep; workflow: Workflow; onChange: (patch: Partial<WorkflowStep>) => void; onDelete: () => void }) {
  return <><div className="inspector-header"><div><div className="eyebrow">STEP PROPERTIES</div><h3>Edit step</h3></div><button className="icon-button" aria-label="Delete step" onClick={onDelete}><MoreHorizontal size={17} /></button></div><div className="inspector-form"><label className="field-label">Step name</label><input value={step.title} onChange={(event) => onChange({ title: event.target.value })} onBlur={(event) => onChange({ title: event.target.value.trim() || "Untitled step" })} /><label className="field-label">Description</label><textarea value={step.description} rows={3} onChange={(event) => onChange({ description: event.target.value })} onBlur={(event) => onChange({ description: event.target.value })} placeholder="What happens in this step?" /><div className="field-pair"><div><label className="field-label">Step type</label><select value={step.step_type} onChange={(event) => onChange({ step_type: event.target.value as StepType })}>{TYPES.map((type) => <option key={type} value={type}>{type.replace("_", " ")}</option>)}</select></div><div><label className="field-label">Status</label><select value={step.status} onChange={(event) => onChange({ status: event.target.value as StepStatus })}>{STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select></div></div><div className="field-pair"><div><label className="field-label">Owner</label><input value={step.owner_role ?? ""} onChange={(event) => onChange({ owner_role: event.target.value || null })} onBlur={(event) => onChange({ owner_role: event.target.value || null })} placeholder="Assign a role" /></div><div><label className="field-label">Duration</label><input value={step.estimated_duration ?? ""} onChange={(event) => onChange({ estimated_duration: event.target.value || null })} onBlur={(event) => onChange({ estimated_duration: event.target.value || null })} placeholder="e.g. 1 day" /></div></div>{step.step_type === "decision" && <><div className="decision-editor"><div className="decision-label"><GitBranch size={14} /> Decision logic</div><label className="field-label">Condition</label><input value={step.condition ?? ""} onChange={(event) => onChange({ condition: event.target.value || null })} onBlur={(event) => onChange({ condition: event.target.value || null })} placeholder="What determines the outcome?" /><div className="field-pair"><div><label className="field-label">If yes, go to</label><select value={step.on_true ?? ""} onChange={(event) => onChange({ on_true: event.target.value || null })}><option value="">Choose a step</option>{workflow.steps.filter((item) => item.id !== step.id).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div><div><label className="field-label">If no, go to</label><select value={step.on_false ?? ""} onChange={(event) => onChange({ on_false: event.target.value || null })}><option value="">Choose a step</option>{workflow.steps.filter((item) => item.id !== step.id).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div></div></div></>}{step.rationale && <div className="rationale-box"><GitFork size={14} /><span>{step.rationale}</span></div>}<div className="inspector-footnote"><CheckCircle2 size={14} /> Changes are checked against workflow rules.</div></div><button className="delete-step-button" onClick={onDelete}><X size={14} /> Remove this step</button></>;
}

function QualityReview({ workflow }: { workflow: Workflow }) {
  const checks = [
    { ok: workflow.steps.length > 0, text: `${workflow.steps.length} workflow steps defined` },
    { ok: workflow.missing_information.length === 0, text: workflow.missing_information.length ? `${workflow.missing_information.length} detail${workflow.missing_information.length > 1 ? "s" : ""} need clarification` : "No critical details missing" },
    { ok: workflow.risks.length === 0, text: workflow.risks.length ? `${workflow.risks.length} potential risk${workflow.risks.length > 1 ? "s" : ""} to review` : "No risks identified" },
  ];
  return <div className="quality-list">{checks.map((check) => <div className="quality-item" key={check.text}><span className={check.ok ? "quality-check" : "quality-warn"}>{check.ok ? <Check size={11} /> : <span>!</span>}</span>{check.text}</div>)}{workflow.missing_information.slice(0, 2).map((item, index) => <div className="quality-detail" key={index}>{item}</div>)}</div>;
}

function ExportMenu({ onExport }: { onExport: (format: string) => void }) {
  const [open, setOpen] = useState(false);
  return <div className="export-menu-wrap"><button className="button button-quiet" onClick={() => setOpen((value) => !value)}><Download size={15} /> Export <ChevronDown size={13} /></button>{open && <><button className="invisible-dismiss" onClick={() => setOpen(false)} aria-label="Close export menu" /><div className="export-menu"><div className="export-group-label">PDF documents</div>{[{ key: "steps_pdf", name: "Steps PDF", detail: "Readable numbered process" }, { key: "flowchart_pdf", name: "Flowchart PDF", detail: "Print-size diagram with branches" }, { key: "pdf", name: "Complete PDF", detail: "Flowchart, steps, and review notes" }].map((item) => <button key={item.key} onClick={() => { setOpen(false); onExport(item.key); }}><span><strong>{item.name}</strong><small>{item.detail}</small></span><ArrowDownToLine size={15} /></button>)}<div className="export-group-label">Other formats</div>{[{ key: "json", name: "JSON", detail: "Workflow data" }, { key: "csv", name: "CSV", detail: "Spreadsheet" }, { key: "markdown", name: "Markdown", detail: "Documentation" }, { key: "mermaid", name: "Mermaid", detail: "Diagram source" }].map((item) => <button key={item.key} onClick={() => { setOpen(false); onExport(item.key); }}><span><strong>{item.name}</strong><small>{item.detail}</small></span><ArrowDownToLine size={15} /></button>)}</div></>}</div>;
}

type RunItem = { id: string; project_id: string; projectTitle: string; started_at: string; finished_at: string | null; outcome: string; transitions: { step_id: string; status: StepStatus; notes: string; at: string }[]; notes: string };
function Runs({ projects, activeProject, setActiveProject, allRuns, onOpen, onStart, onUpdate, onFinish, notes, setNotes }: { projects: Project[]; activeProject: Project | null; setActiveProject: (project: Project) => void; allRuns: RunItem[]; onOpen: (project: Project) => void; onStart: () => void; onUpdate: (step: WorkflowStep, status: StepStatus, notes: string) => void; onFinish: () => void; notes: string; setNotes: (value: string) => void }) {
  const activeRun = activeProject?.runs.find((run) => run.outcome === "in_progress");
  const [selectedProject, setSelectedProject] = useState(activeProject?.id ?? projects[0]?.id ?? "");
  useEffect(() => { if (activeProject) setSelectedProject(activeProject.id); }, [activeProject]);
  const chosen = projects.find((project) => project.id === selectedProject) ?? activeProject;
  const changeProject = (id: string) => { setSelectedProject(id); const project = projects.find((item) => item.id === id); if (project) setActiveProject(project); };
  return <div className="page-content runs-page"><div className="page-heading"><div><div className="eyebrow">OPERATIONAL TRACKING</div><h1>Workflow runs</h1><p>Follow work as it moves through each stage. Progress is saved with a complete audit trail.</p></div>{chosen && !activeRun && <button className="button button-primary" onClick={onStart}><Play size={15} /> Start a run</button>}</div><div className="run-layout"><section className="run-active-card"><div className="run-card-heading"><div><div className="eyebrow">CURRENT WORKFLOW</div><h2>{chosen ? titleOf(chosen) : "Choose a workflow"}</h2></div>{chosen && <select className="run-workflow-select" value={chosen.id} onChange={(event) => changeProject(event.target.value)}>{projects.map((project) => <option key={project.id} value={project.id}>{titleOf(project)}</option>)}</select>}</div>{chosen ? activeRun ? <><div className="active-run-banner"><span className="live-pulse" /> Run in progress <span>Started {timeLabel(activeRun.started_at)}</span></div><div className="run-checklist">{chosen.workflow.steps.map((step, index) => <RunStep step={step} index={index} onUpdate={onUpdate} key={step.id} />)}</div><div className="finish-run-form"><label className="field-label">Run notes</label><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Add a closing note or outcome…" /><button className="button button-primary" onClick={onFinish}><CheckCircle2 size={15} /> Complete run</button></div></> : <div className="no-active-run"><div className="empty-illustration"><Play size={21} /></div><h3>Ready when you are</h3><p>Start a run to track step-by-step progress for <strong>{titleOf(chosen)}</strong>.</p><button className="button button-primary" onClick={onStart}><Play size={15} /> Start a run</button></div> : <div className="no-active-run"><div className="empty-illustration"><WorkflowIcon size={21} /></div><h3>No workflow selected</h3><p>Create a workflow to start tracking its progress.</p></div>}</section><aside className="run-history-card"><div className="section-heading"><div><div className="eyebrow">AUDIT TRAIL</div><h3>Recent runs</h3></div><span className="starter-count">{allRuns.length}</span></div>{allRuns.length ? <div className="run-history-list">{allRuns.slice(0, 12).map((run) => <button className="run-history-item" key={run.id} onClick={() => { const project = projects.find((item) => item.id === run.project_id); if (project) onOpen(project); }}><span className={`run-history-icon ${run.outcome === "completed" ? "complete" : "inprogress"}`}>{run.outcome === "completed" ? <Check size={14} /> : <Play size={13} />}</span><span className="run-history-copy"><strong>{run.projectTitle}</strong><small>{timeLabel(run.started_at)} · {run.transitions.length} updates</small></span><span className={`run-outcome outcome-${run.outcome}`}>{run.outcome.replace("_", " ")}</span></button>)}</div> : <div className="history-empty">Completed and active runs will appear here.</div>}</aside></div></div>;
}

function RunStep({ step, index, onUpdate }: { step: WorkflowStep; index: number; onUpdate: (step: WorkflowStep, status: StepStatus, notes: string) => void }) {
  const [notes, setNotes] = useState(step.notes);
  return <div className={`run-step ${step.status === "done" ? "is-done" : ""}`}><span className={`run-step-index status-${step.status}`}>{step.status === "done" ? <Check size={14} /> : String(index + 1).padStart(2, "0")}</span><div className="run-step-content"><strong>{step.title}</strong><small>{step.owner_role || step.step_type.replace("_", " ")}</small><input value={notes} onChange={(event) => setNotes(event.target.value)} onBlur={() => { if (notes !== step.notes) onUpdate(step, step.status, notes); }} placeholder="Add a note (optional)" /></div><select value={step.status} onChange={(event) => onUpdate(step, event.target.value as StepStatus, notes)}>{STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select></div>;
}

function Analytics({ projects, runs }: { projects: Project[]; runs: RunItem[] }) {
  const domains = new Map<string, number>();
  projects.forEach((project) => { const key = project.workflow.domain || "General"; domains.set(key, (domains.get(key) ?? 0) + 1); });
  const types = new Map<string, number>();
  projects.flatMap((project) => project.workflow.steps).forEach((step) => types.set(step.step_type, (types.get(step.step_type) ?? 0) + 1));
  const maxDomain = Math.max(...domains.values(), 1); const maxType = Math.max(...types.values(), 1);
  const totalSteps = projects.reduce((sum, project) => sum + project.workflow.steps.length, 0);
  const totalDone = projects.reduce((sum, project) => sum + countDone(project), 0);
  const completeRuns = runs.filter((run) => run.outcome === "completed").length;
  const avgSteps = projects.length ? (totalSteps / projects.length).toFixed(1) : "0";
  return <div className="page-content analytics-page"><div className="page-heading"><div><div className="eyebrow">WORKSPACE INSIGHTS</div><h1>Understand how work flows.</h1><p>Operational signals across your saved process blueprints and run history.</p></div><span className="heading-badge"><Activity size={14} /> Live workspace data</span></div><div className="stat-grid analytics-stats"><StatCard icon={<WorkflowIcon size={17} />} label="Workflows" value={projects.length} meta="In your library" tint="violet" /><StatCard icon={<Boxes size={17} />} label="Defined steps" value={totalSteps} meta={`${avgSteps} average per workflow`} tint="blue" /><StatCard icon={<Play size={16} />} label="Total runs" value={runs.length} meta={`${completeRuns} completed`} tint="green" /><StatCard icon={<CheckCircle2 size={17} />} label="Steps completed" value={totalDone} meta="Across all workflows" tint="amber" /></div><div className="analytics-grid"><section className="analytics-card"><div className="section-heading"><div><h3>Workflows by domain</h3><p>Where your processes live</p></div><BarChart3 size={17} /></div>{domains.size ? <div className="bar-list">{[...domains.entries()].sort((a, b) => b[1] - a[1]).map(([name, count]) => <div className="bar-row" key={name}><span>{name}</span><div className="bar-track"><i style={{ width: `${Math.max(8, (count / maxDomain) * 100)}%` }} /></div><b>{count}</b></div>)}</div> : <p className="chart-empty">Create a workflow to see the domain breakdown.</p>}</section><section className="analytics-card"><div className="section-heading"><div><h3>Step composition</h3><p>Types used across your workflows</p></div><GitFork size={17} /></div>{types.size ? <div className="bar-list">{[...types.entries()].sort((a, b) => b[1] - a[1]).map(([name, count]) => <div className="bar-row" key={name}><span className="capitalize">{name}</span><div className="bar-track"><i className="bar-blue" style={{ width: `${Math.max(8, (count / maxType) * 100)}%` }} /></div><b>{count}</b></div>)}</div> : <p className="chart-empty">Generated steps will be categorized here.</p>}</section></div><section className="analytics-card recent-runs-table"><div className="section-heading"><div><h3>Recent workflow runs</h3><p>Execution history across your workspace</p></div><Clock3 size={17} /></div>{runs.length ? <div className="table-wrap"><table><thead><tr><th>WORKFLOW</th><th>STARTED</th><th>UPDATES</th><th>OUTCOME</th></tr></thead><tbody>{runs.slice(0, 10).map((run) => <tr key={run.id}><td>{run.projectTitle}</td><td>{timeLabel(run.started_at)}</td><td>{run.transitions.length}</td><td><span className={`run-outcome outcome-${run.outcome}`}>{run.outcome.replace("_", " ")}</span></td></tr>)}</tbody></table></div> : <p className="chart-empty">No runs recorded yet. Start one from any workflow canvas.</p>}</section></div>;
}

function CommandDialog({ projects, onClose, onNavigate, onOpen }: { projects: Project[]; onClose: () => void; onNavigate: (view: View) => void; onOpen: (project: Project) => void }) {
  const [query, setQuery] = useState("");
  const actions: { name: string; hint: string; action: () => void; icon: ReactNode }[] = [
    { name: "Go to overview", hint: "Workspace", action: () => onNavigate("overview"), icon: <LayoutDashboard size={15} /> },
    { name: "Browse workflows", hint: "Library", action: () => onNavigate("library"), icon: <Boxes size={15} /> },
    { name: "View run history", hint: "Operations", action: () => onNavigate("runs"), icon: <Activity size={15} /> },
    { name: "Open analytics", hint: "Insights", action: () => onNavigate("analytics"), icon: <BarChart3 size={15} /> },
  ];
  const matches = projects.filter((project) => titleOf(project).toLowerCase().includes(query.toLowerCase())).slice(0, 5);
  return <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="command-dialog"><div className="command-input"><Search size={17} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search workflows or jump to…" /><kbd>ESC</kbd></div><div className="command-results"><div className="command-label">QUICK NAVIGATION</div>{actions.filter((action) => action.name.toLowerCase().includes(query.toLowerCase())).map((action) => <button key={action.name} onClick={action.action}>{action.icon}<span>{action.name}</span><small>{action.hint}</small><ArrowRight size={14} /></button>)}{matches.length > 0 && <><div className="command-label">WORKFLOWS</div>{matches.map((project) => <button key={project.id} onClick={() => onOpen(project)}><WorkflowIcon size={15} /><span>{titleOf(project)}</span><small>{project.workflow.domain}</small><ArrowRight size={14} /></button>)}</>}</div><div className="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span><span><kbd>↵</kbd> Open</span><span><Command size={12} /> Quick switch</span></div></section></div>;
}

export default function AppRoot() { return <ReactFlowProvider><App /></ReactFlowProvider>; }
