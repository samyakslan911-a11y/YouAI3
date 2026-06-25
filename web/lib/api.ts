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
  published?: Record<string, string>;
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

  scheduleClip: (filename: string, publishAt: string, platform = "youtube") =>
    apiFetch<{ id: string; filename: string; publish_at: string; status: string }>(`/api/clips/${encodeURIComponent(filename)}/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ publish_at: publishAt, platform }),
    }),

  listSchedule: () =>
    apiFetch<{ id: string; filename: string; platform: string; publish_at: string; status: string; result_url: string; error: string }[]>("/api/schedule"),

  cancelSchedule: (id: string) =>
    apiFetch<{ cancelled: string }>(`/api/schedule/${id}`, { method: "DELETE" }),

  publishClip: (filename: string, platform = "youtube") =>
    apiFetch<{ platform: string; url: string }>(`/api/clips/${encodeURIComponent(filename)}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform }),
    }),

  getPlatforms: () =>
    apiFetch<Record<string, { configured: boolean; label: string; hint: string }>>("/api/platforms"),

  analytics: (days = 28) => apiFetch<{ report: Record<string, unknown>[] }>(`/api/analytics?days=${days}`),

  analyticsInsights: (days = 28) =>
    apiFetch<{ insights: string[] }>(`/api/analytics/insights?days=${days}`, { method: "POST" }),

  createSlides: (topic: string, style: string, series_part?: number, profile_id?: string) =>
    apiFetch<{ job_id: string }>("/api/slides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, style, series_part, profile_id: profile_id ?? "" }),
    }),

  listSlides: () =>
    apiFetch<{ sets: { slug: string; topic: string; style: string; title: string; created_at: string; image_count: number; has_video: boolean }[] }>("/api/slides"),

  getSlides: (slug: string) =>
    apiFetch<{
      slug: string; topic: string; style: string; title: string;
      images: string[]; video: string | null;
      hashtags: Record<string, string[]>;
      hook_variants: string[];
      created_at: string;
    }>(`/api/slides/${slug}`),

  slideImageUrl: (slug: string, filename: string) => `${BASE}/api/slides/${slug}/images/${filename}`,
  slideVideoUrl: (slug: string) => `${BASE}/api/slides/${slug}/video`,
  slideZipUrl: (slug: string) => `${BASE}/api/slides/${slug}/zip`,

  listProfiles: () =>
    apiFetch<ProfileItem[]>("/api/profiles"),

  createProfile: (name: string) =>
    apiFetch<ProfileItem>("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),

  deleteProfile: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/profiles/${id}`, { method: "DELETE" }),

  saveBrandKit: (
    id: string,
    kit: { accent_hex?: string | null; base_hue?: string | null; darkness?: string | null; font?: string | null; voice?: string | null }
  ) =>
    apiFetch<ProfileItem>(`/api/profiles/${id}/brand-kit`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(kit),
    }),

  listStyles: () =>
    apiFetch<{ styles: StyleItem[] }>("/api/styles"),

  createStyle: (name: string, accent_hex: string, base_hue: string, darkness: string) =>
    apiFetch<StyleItem>("/api/styles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, accent_hex, base_hue, darkness }),
    }),

  deleteStyle: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/styles/${id}`, { method: "DELETE" }),
};

export type ProfileItem = {
  id: string;
  name: string;
  expert_context: string;
  style: string;
  content_angles: string[];
  image_keywords: string[];
  created_at: string;
  // Brand Kit (optional)
  brand_accent_hex?: string | null;
  brand_base_hue?: string | null;
  brand_darkness?: string | null;
  brand_font?: string | null;
  brand_voice?: string | null;
};

export type StyleItem = {
  id: string;
  name: string;
  accent_hex: string;
  is_custom: boolean;
  base_hue?: string;
  darkness?: string;
};
