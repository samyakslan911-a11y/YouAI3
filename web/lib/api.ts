const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

export type Video = {
  id: string;
  url: string;
  title: string;
  channel_name: string;
  views: number;
  channel_avg_views: number;
  outlier_ratio: number;
  duration_s: number;
  published: string;
};

export type Clip = {
  filename: string;
  size_mb: number;
  modified?: number;
  title?: string;
  hook?: string;
  score?: number;
  virality_reason?: string;
  thumbnail?: string;
};

export type Job = {
  status: "queued" | "running" | "done" | "error";
  logs: string[];
  clips: { filename: string; title: string; hook: string; start: number; end: number }[];
  error?: string;
};

export const api = {
  research: (query: string, opts?: { ratio?: number; lang?: string; cc?: boolean }) =>
    apiFetch<{ videos: Video[] }>(
      `/api/research?query=${encodeURIComponent(query)}&min_ratio=${opts?.ratio ?? 3}&language=${opts?.lang ?? "es"}&cc_only=${opts?.cc ?? false}`
    ),

  createJob: (url: string, opts?: { captionStyle?: string; faceTrack?: boolean }) =>
    apiFetch<{ job_id: string }>("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        dry_run: false,
        caption_style: opts?.captionStyle ?? "capcut",
        face_track: opts?.faceTrack ?? true,
      }),
    }),

  createQueue: (urls: string[], opts?: { captionStyle?: string; faceTrack?: boolean }) =>
    apiFetch<{ job_ids: string[] }>("/api/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        urls,
        dry_run: false,
        caption_style: opts?.captionStyle ?? "capcut",
        face_track: opts?.faceTrack ?? true,
      }),
    }),

  listJobs: () => apiFetch<{ id: string; url: string; status: string; clips: unknown[]; error: string }[]>("/api/jobs"),

  getJob: (id: string) => apiFetch<Job>(`/api/jobs/${id}`),

  listClips: () => apiFetch<{ clips: Clip[] }>("/api/clips"),

  clipUrl: (filename: string) => `${BASE}/api/clips/${filename}`,

  thumbnailUrl: (thumbnail: string) => `${BASE}/api/clips/${thumbnail}`,

  regenThumbnail: (filename: string) =>
    apiFetch<{ thumbnail: string }>(`/api/clips/${encodeURIComponent(filename)}/thumbnail`, { method: "POST" }),

  publishClip: (filename: string, platform = "youtube") =>
    apiFetch<{ platform: string; url: string }>(`/api/clips/${encodeURIComponent(filename)}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform }),
    }),

  analytics: (days = 28) => apiFetch<{ report: Record<string, unknown>[] }>(`/api/analytics?days=${days}`),
};
