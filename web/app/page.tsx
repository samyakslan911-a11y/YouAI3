"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { api, type Video, type Job } from "@/lib/api";
import {
  Search, Zap, Video as VideoIcon, BarChart2, TrendingUp,
  Download, ChevronDown, Clock, Eye, ThumbsUp, Play, Loader2,
  ArrowRight, Sparkles, Radio, ChevronRight, Upload, ExternalLink,
  CalendarClock, CheckCircle2, XCircle, Trash2,
} from "lucide-react";

// ── helpers ───────────────────────────────────────────────────────────────────
function fmt(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}
function fmtDur(s: number) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// ── animation variants ────────────────────────────────────────────────────────
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.4 } },
};
const stagger: Variants = {
  show: { transition: { staggerChildren: 0.07 } },
};

// ── nav ───────────────────────────────────────────────────────────────────────
const NAV = [
  { id: "discover",  label: "Descubrir",  Icon: Search },
  { id: "process",   label: "Procesar",   Icon: Zap },
  { id: "clips",     label: "Clips",      Icon: VideoIcon },
  { id: "analytics", label: "Analytics",  Icon: BarChart2 },
];

const SUGGESTIONS = [
  "historia curiosidades", "gaming reacción", "ciencia sorprendente",
  "misterios inexplicables", "finanzas personales", "true crime español",
];

// ── root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [active, setActive] = useState("discover");
  // Shared state: URL lifted so Discover → Process works without DOM hacks
  const [processUrl, setProcessUrl] = useState("");
  // Version counter: incremented when a job finishes to refresh the clips gallery
  const [clipsVersion, setClipsVersion] = useState(0);

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id); }),
      { rootMargin: "-35% 0px -55% 0px" }
    );
    NAV.forEach(({ id }) => { const el = document.getElementById(id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, []);

  function go(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handleSelectVideo(url: string) {
    setProcessUrl(url);
    setTimeout(() => go("process"), 50);
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">

      {/* ── sticky nav ───────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 px-6 py-3 flex items-center gap-6 border-b border-white/[0.05] backdrop-blur-2xl bg-zinc-950/75">
        <button onClick={() => go("discover")} className="text-lg font-bold tracking-tight shrink-0 select-none">
          <span className="grad-text">You</span>
          <span>AI3</span>
        </button>
        <nav className="flex gap-1">
          {NAV.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => go(id)}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all duration-200 ${
                active === id ? "text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {active === id && (
                <motion.span
                  layoutId="nav-pill"
                  className="absolute inset-0 bg-white/[0.07] rounded-lg"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
                />
              )}
              <Icon size={13} className="relative z-10" />
              <span className="relative z-10">{label}</span>
            </button>
          ))}
        </nav>
      </header>

      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <section className="relative min-h-[88vh] flex flex-col items-center justify-center text-center px-6 overflow-hidden">
        {/* background blobs */}
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-red-600/10 rounded-full blur-3xl pointer-events-none"
          style={{ animation: "float 8s ease-in-out infinite" }} />
        <div className="absolute -bottom-20 -right-20 w-80 h-80 bg-violet-600/8 rounded-full blur-3xl pointer-events-none"
          style={{ animation: "float 10s ease-in-out infinite reverse" }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-red-900/5 rounded-full blur-3xl pointer-events-none" />

        {/* grid pattern */}
        <div className="absolute inset-0 opacity-[0.025] pointer-events-none"
          style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)", backgroundSize: "64px 64px" }} />

        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }} className="w-full max-w-2xl">
          <div className="inline-flex items-center gap-2 glass border border-red-500/20 text-red-400 text-xs px-4 py-2 rounded-full mb-8">
            <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
            <Sparkles size={11} />
            Pipeline de contenido viral · Potenciado por Gemini AI
          </div>

          <h1 className="text-6xl sm:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
            Convierte videos en<br />
            <span className="grad-text">clips virales</span>
          </h1>

          <p className="text-zinc-400 max-w-lg mx-auto mb-8 text-lg leading-relaxed">
            Pega un link de YouTube, la IA encuentra los momentos virales y genera Shorts en 9:16 listos para publicar.
          </p>

          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => go("process")}
              className="group flex items-center gap-2.5 bg-red-600 hover:bg-red-500 text-white font-semibold px-7 py-3.5 rounded-2xl transition-all duration-200 hover:scale-105 hover:shadow-[0_0_30px_rgba(239,68,68,0.4)]"
            >
              Generar clips
              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
            <button
              onClick={() => go("discover")}
              className="flex items-center gap-2 glass glass-hover text-zinc-300 px-6 py-3.5 rounded-2xl transition-all text-sm font-medium"
            >
              <Search size={14} className="text-red-400" />
              Buscar outliers
            </button>
          </div>
        </motion.div>

        {/* floating stats */}
        <motion.div
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5, duration: 0.6 }}
          className="absolute right-8 top-1/2 -translate-y-1/2 hidden xl:flex flex-col gap-3"
        >
          {[
            { label: "Outlier ratio", val: "94.7x", color: "text-red-400" },
            { label: "Clips/video",   val: "5",     color: "text-violet-400" },
            { label: "Tiempo/clip",   val: "~25s",  color: "text-green-400" },
          ].map(({ label, val, color }) => (
            <div key={label} className="glass grad-border rounded-xl px-4 py-3 text-right">
              <p className={`text-xl font-bold ${color}`}>{val}</p>
              <p className="text-xs text-zinc-600">{label}</p>
            </div>
          ))}
        </motion.div>

        <button onClick={() => go("discover")} className="absolute bottom-8 left-1/2 -translate-x-1/2 text-zinc-700 hover:text-zinc-500 transition-colors animate-bounce">
          <ChevronDown size={22} />
        </button>
      </section>

      {/* ── content ──────────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-6 pb-32 space-y-28">

        <section id="discover" className="scroll-mt-20">
          <SectionLabel Icon={Search} label="Descubrir" />
          <DiscoverSection onSelectVideo={handleSelectVideo} />
        </section>

        <WaveDivider />

        <section id="process" className="scroll-mt-20">
          <SectionLabel Icon={Zap} label="Procesar video" />
          <ProcessSection
            url={processUrl}
            setUrl={setProcessUrl}
            onJobDone={() => setClipsVersion((v) => v + 1)}
          />
        </section>

        <WaveDivider />

        <section id="clips" className="scroll-mt-20">
          <SectionLabel Icon={VideoIcon} label="Mis clips" />
          <ClipsSection refreshKey={clipsVersion} />
        </section>

        <WaveDivider />

        <section id="schedule" className="scroll-mt-20">
          <SectionLabel Icon={CalendarClock} label="Programados" />
          <ScheduleSection />
        </section>

        <WaveDivider />

        <section id="analytics" className="scroll-mt-20">
          <SectionLabel Icon={BarChart2} label="Analytics" />
          <AnalyticsSection />
        </section>
      </div>
    </div>
  );
}

type ScheduledJob = {
  id: string; filename: string; platform: string;
  publish_at: string; status: string; result_url: string; error: string;
};

function ScheduleSection() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try { setJobs(await api.listSchedule()); } catch { /* ignore */ }
    finally { setLoading(false); }
  }

  async function cancel(id: string) {
    try { await api.cancelSchedule(id); load(); } catch { /* ignore */ }
  }

  useEffect(() => { load(); }, []);

  // poll pending/running jobs
  useEffect(() => {
    if (!jobs.some(j => j.status === "pending" || j.status === "running")) return;
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, [jobs.map(j => j.id + j.status).join(",")]);

  function fmtDate(iso: string) {
    try {
      return new Intl.DateTimeFormat(undefined, {
        dateStyle: "short", timeStyle: "short",
      }).format(new Date(iso));
    } catch { return iso; }
  }

  if (loading) return <div className="shimmer h-20 rounded-2xl" />;

  if (!jobs.length) return (
    <div className="glass rounded-2xl py-14 text-center border-dashed">
      <CalendarClock size={32} className="mx-auto mb-3 text-zinc-700" />
      <p className="text-zinc-500 text-sm">Sin publicaciones programadas</p>
      <p className="text-zinc-700 text-xs mt-1">Usa el botón "Programar" en cualquier clip</p>
    </div>
  );

  return (
    <div className="space-y-2">
      {jobs.map(j => (
        <motion.div key={j.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          className="glass rounded-xl px-4 py-3 flex items-center gap-4">
          {/* status icon */}
          {j.status === "done"
            ? <CheckCircle2 size={16} className="text-green-400 shrink-0" />
            : j.status === "error"
            ? <XCircle size={16} className="text-red-400 shrink-0" />
            : j.status === "running"
            ? <Loader2 size={16} className="text-yellow-400 animate-spin shrink-0" />
            : j.status === "cancelled"
            ? <XCircle size={16} className="text-zinc-600 shrink-0" />
            : <Clock size={16} className="text-zinc-500 shrink-0" />}

          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-zinc-200 truncate">{j.filename.replace(/_final\.mp4$/, "").replace(/_/g, " ")}</p>
            <p className="text-[10px] text-zinc-600">
              {j.status === "done"
                ? <a href={j.result_url} target="_blank" rel="noreferrer" className="text-green-400 hover:underline">{j.result_url}</a>
                : j.status === "error" ? <span className="text-red-400/80">{j.error.slice(0, 80)}</span>
                : j.status === "cancelled" ? "Cancelado"
                : `Programado: ${fmtDate(j.publish_at)}`}
            </p>
          </div>

          <span className={`text-[10px] px-2 py-0.5 rounded-full border shrink-0 ${
            j.status === "done" ? "bg-green-500/10 border-green-500/20 text-green-400" :
            j.status === "error" ? "bg-red-500/10 border-red-500/20 text-red-400" :
            j.status === "running" ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-400" :
            j.status === "cancelled" ? "bg-zinc-800 border-zinc-700 text-zinc-600" :
            "bg-zinc-800 border-zinc-700 text-zinc-400"
          }`}>
            {j.status}
          </span>

          {j.status === "pending" && (
            <button onClick={() => cancel(j.id)} className="text-zinc-700 hover:text-red-400 transition-colors">
              <Trash2 size={13} />
            </button>
          )}
        </motion.div>
      ))}
    </div>
  );
}

function ScheduleButton({ filename }: { filename: string }) {
  const [open, setOpen] = useState(false);
  const [dt, setDt] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");

  // default to tomorrow same time
  function openPicker() {
    const d = new Date(Date.now() + 24 * 3600 * 1000);
    d.setSeconds(0, 0);
    setDt(d.toISOString().slice(0, 16));
    setState("idle");
    setMsg("");
    setOpen(true);
  }

  async function submit() {
    if (!dt) return;
    setState("loading");
    try {
      await api.scheduleClip(filename, dt + ":00");
      setState("done");
      setMsg("Programado");
      setTimeout(() => setOpen(false), 1500);
    } catch (e: unknown) {
      setState("error");
      setMsg(e instanceof Error ? e.message.slice(0, 60) : "Error");
    }
  }

  if (!open) return (
    <button onClick={openPicker}
      className="flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-300 transition-colors">
      <Clock size={10} /> Programar
    </button>
  );

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <input type="datetime-local" value={dt} onChange={e => setDt(e.target.value)}
        className="text-xs bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1 text-zinc-300 focus:outline-none focus:ring-1 focus:ring-red-500/40" />
      <button onClick={submit} disabled={state === "loading" || !dt}
        className="flex items-center gap-1 text-xs bg-red-600/80 hover:bg-red-600 disabled:opacity-40 text-white px-2.5 py-1 rounded-lg transition-colors">
        {state === "loading" ? <Loader2 size={10} className="animate-spin" /> : <Clock size={10} />}
        {state === "done" ? msg : state === "error" ? msg : "OK"}
      </button>
      <button onClick={() => setOpen(false)} className="text-zinc-600 hover:text-zinc-400 text-xs px-1">×</button>
    </div>
  );
}

function PublishButton({ filename }: { filename: string }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");

  async function publish() {
    setState("loading");
    try {
      const res = await api.publishClip(filename, "youtube");
      setUrl(res.url);
      setState("done");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Error al publicar");
      setState("error");
    }
  }

  if (state === "done") return (
    <a href={url} target="_blank" rel="noreferrer"
      className="flex items-center gap-1.5 text-xs bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-xl transition-colors w-fit font-medium">
      <ExternalLink size={10} /> Ver en YouTube
    </a>
  );

  if (state === "error") return (
    <p className="text-[10px] text-red-400/80 line-clamp-2" title={err}>
      {err.includes("Credenciales") ? "YouTube no configurado" : err.slice(0, 60)}
    </p>
  );

  return (
    <button onClick={publish} disabled={state === "loading"}
      className="flex items-center gap-1.5 text-xs bg-zinc-800 hover:bg-red-600 disabled:opacity-40 text-zinc-400 hover:text-white border border-zinc-700 hover:border-red-500 px-3 py-1.5 rounded-xl transition-all w-fit font-medium group">
      {state === "loading"
        ? <Loader2 size={10} className="animate-spin" />
        : <Upload size={10} className="group-hover:scale-110 transition-transform" />}
      {state === "loading" ? "Publicando…" : "Publicar"}
    </button>
  );
}

function ScoreBadge({ score, reason }: { score?: number; reason?: string }) {
  if (score == null) return null;
  const color = score >= 90 ? "text-green-400 bg-green-500/10 border-green-500/20"
    : score >= 70 ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20"
    : "text-zinc-400 bg-zinc-800 border-zinc-700";
  return (
    <div className={`flex items-center gap-1.5 border rounded-lg px-2 py-1 ${color}`} title={reason}>
      <span className="text-xs font-bold tabular-nums">{score}</span>
      <div className="flex gap-0.5">
        {[...Array(5)].map((_, i) => (
          <span key={i} className={`w-1 rounded-sm ${i < Math.round(score / 20) ? "opacity-100" : "opacity-20"}`}
            style={{ height: `${6 + i * 2}px`, background: "currentColor" }} />
        ))}
      </div>
    </div>
  );
}

function SectionLabel({ Icon, label }: { Icon: React.ElementType; label: string }) {
  return (
    <div className="flex items-center gap-3 mb-8">
      <div className="relative">
        <div className="absolute inset-0 bg-red-500/20 rounded-xl blur-sm" />
        <div className="relative bg-red-500/10 border border-red-500/20 p-2.5 rounded-xl">
          <Icon size={16} className="text-red-400" />
        </div>
      </div>
      <h2 className="text-2xl font-bold">{label}</h2>
    </div>
  );
}

function WaveDivider() {
  return (
    <div className="relative h-px">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-zinc-700/40 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-red-500/10 to-transparent blur-sm" />
    </div>
  );
}

// ── Discover ──────────────────────────────────────────────────────────────────
function DiscoverSection({ onSelectVideo }: { onSelectVideo: (url: string) => void }) {
  const [query, setQuery] = useState("");
  const [ratio, setRatio] = useState(3);
  const [cc, setCc] = useState(false);
  const [loading, setLoading] = useState(false);
  const [videos, setVideos] = useState<Video[]>([]);
  const [error, setError] = useState("");

  async function search(q = query) {
    if (!q.trim()) return;
    setQuery(q);
    setLoading(true);
    setError("");
    setVideos([]);
    try {
      const res = await api.research(q, { ratio, cc });
      setVideos(res.videos);
      if (!res.videos.length) setError("No se encontraron outliers. Prueba reducir el ratio.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al buscar");
    } finally {
      setLoading(false);
    }
  }

  const maxRatio = Math.max(...videos.map((v) => v.outlier_ratio), 1);

  return (
    <div className="space-y-5">
      {/* search bar */}
      <div className="glass grad-border rounded-2xl p-4 flex gap-3 flex-wrap items-center">
        <div className="flex-1 min-w-60 relative">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder='Ej: "historia curiosidades", "gaming reacción"'
            className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-red-500/40 focus:border-red-500/40 transition"
          />
        </div>
        <div className="flex items-center gap-2 bg-zinc-900/60 border border-zinc-800 rounded-xl px-3.5 py-2.5">
          <TrendingUp size={13} className="text-zinc-600" />
          <span className="text-xs text-zinc-500 whitespace-nowrap">Ratio ≥</span>
          <input type="number" value={ratio} onChange={(e) => setRatio(Number(e.target.value))}
            className="w-10 bg-transparent text-sm text-center focus:outline-none font-medium" min={1} step={0.5} />
          <span className="text-xs text-zinc-600">x</span>
        </div>
        <label className="flex items-center gap-2 bg-zinc-900/60 border border-zinc-800 rounded-xl px-3.5 py-2.5 cursor-pointer">
          <input type="checkbox" checked={cc} onChange={(e) => setCc(e.target.checked)} className="accent-red-500" />
          <span className="text-xs text-zinc-400">CC only</span>
        </label>
        <button onClick={() => search()} disabled={loading}
          className="flex items-center gap-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-all hover:shadow-[0_0_20px_rgba(239,68,68,0.35)] hover:scale-105 active:scale-95">
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
          Buscar
        </button>
      </div>

      {/* suggestions */}
      <div className="flex gap-2 flex-wrap">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => search(s)}
            className="group text-xs glass glass-hover border-white/[0.05] text-zinc-500 hover:text-zinc-200 px-3 py-1.5 rounded-full transition-all hover:border-red-500/20 flex items-center gap-1">
            <ChevronRight size={10} className="opacity-0 group-hover:opacity-100 -ml-1 transition-all" />
            {s}
          </button>
        ))}
      </div>

      {error && <p className="text-red-400/80 text-sm bg-red-500/5 border border-red-500/10 rounded-xl px-4 py-3">{error}</p>}

      {loading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="shimmer h-20 rounded-2xl" style={{ opacity: 1 - i * 0.15 }} />
          ))}
        </div>
      )}

      <AnimatePresence>
        {!loading && videos.length > 0 && (
          <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-2.5">
            <p className="text-xs text-zinc-600 uppercase tracking-widest font-medium px-1">{videos.length} outliers</p>
            {videos.map((v, i) => (
              <motion.div key={v.id} variants={fadeUp}
                className="group glass glass-hover grad-border rounded-2xl p-4 flex gap-4 items-start cursor-default">
                <span className="text-zinc-700 text-xs font-mono w-5 pt-1 shrink-0">#{i + 1}</span>
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-medium text-sm leading-snug text-zinc-200">{v.title}</p>
                    <span className="shrink-0 text-red-400 text-sm font-bold px-2.5 py-0.5 bg-red-500/10 border border-red-500/15 rounded-full tabular-nums">
                      {v.outlier_ratio}×
                    </span>
                  </div>
                  {/* ratio bar */}
                  <div className="h-0.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div className="ratio-bar h-full" style={{ width: `${Math.min((v.outlier_ratio / maxRatio) * 100, 100)}%` }} />
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-zinc-600">
                    <span className="flex items-center gap-1 text-zinc-400 font-medium"><Eye size={10} />{fmt(v.views)}</span>
                    <span>avg {fmt(v.channel_avg_views)}</span>
                    <span className="flex items-center gap-1"><Clock size={10} />{fmtDur(v.duration_s)}</span>
                    <span>{v.channel_name} · {v.published}</span>
                  </div>
                </div>
                <button onClick={() => onSelectVideo(v.url)}
                  className="shrink-0 opacity-0 group-hover:opacity-100 flex items-center gap-1.5 bg-red-600 hover:bg-red-500 text-white text-xs px-3.5 py-2 rounded-xl transition-all font-medium hover:shadow-[0_0_15px_rgba(239,68,68,0.4)]">
                  Usar <ArrowRight size={11} />
                </button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Process ───────────────────────────────────────────────────────────────────
type ActiveJob = {
  id: string;
  url: string;
  status: string;
  logs: string[];
  clips: { filename: string; title: string; hook: string; score?: number; virality_reason?: string }[];
  error?: string;
};

function urlLabel(u: string) {
  try {
    const parts = new URL(u).hostname.replace("www.", "") + new URL(u).pathname;
    return parts.length > 40 ? parts.slice(0, 40) + "…" : parts;
  } catch { return u.length > 50 ? u.slice(0, 50) + "…" : u; }
}

function JobStatusDot({ status }: { status: string }) {
  if (status === "done") return <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />;
  if (status === "error") return <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />;
  if (status === "running") return <span className="w-2 h-2 rounded-full bg-yellow-400 shrink-0 animate-pulse" />;
  return <span className="w-2 h-2 rounded-full bg-zinc-700 shrink-0" />;
}

function stepFromLogs(logs: string[]) {
  if (logs.some(l => l.includes("Clip listo"))) return 3;
  if (logs.some(l => l.includes("virales"))) return 2;
  if (logs.some(l => l.includes("Transcripción"))) return 1;
  if (logs.some(l => l.includes("Descargando") || l.includes("cache"))) return 0;
  return -1;
}

function ProcessSection({
  url, setUrl, onJobDone,
}: {
  url: string;
  setUrl: (u: string) => void;
  onJobDone: () => void;
}) {
  const [pendingUrls, setPendingUrls] = useState<string[]>([]);
  const [jobs, setJobs] = useState<ActiveJob[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [captionStyle, setCaptionStyle] = useState<"capcut" | "subtitles" | "none">("capcut");
  const [faceTrack, setFaceTrack] = useState(true);
  const logsRef = useRef<HTMLDivElement>(null);

  function addUrl() {
    const u = url.trim();
    if (!u || pendingUrls.includes(u)) return;
    setPendingUrls(prev => [...prev, u]);
    setUrl("");
  }

  function removeUrl(u: string) {
    setPendingUrls(prev => prev.filter(x => x !== u));
  }

  async function submitUrls(urls: string[]) {
    if (!urls.length) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await api.createQueue(urls, { captionStyle, faceTrack });
      const newJobs: ActiveJob[] = res.job_ids.map((id, i) => ({
        id, url: urls[i], status: "queued", logs: [], clips: [],
      }));
      setJobs(prev => [...newJobs, ...prev]);
      setActiveJobId(res.job_ids[0]);
      setPendingUrls([]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al iniciar la cola");
      setSubmitting(false);
    }
  }

  function processQueue() { submitUrls(pendingUrls); }

  // poll all active jobs
  useEffect(() => {
    const activeIds = jobs.filter(j => j.status === "queued" || j.status === "running").map(j => j.id);
    if (!activeIds.length) {
      setSubmitting(false);
      return;
    }
    const iv = setInterval(async () => {
      const updates = await Promise.allSettled(activeIds.map(id => api.getJob(id)));
      let anyDone = false;
      setJobs(prev => prev.map(j => {
        const idx = activeIds.indexOf(j.id);
        if (idx < 0) return j;
        const res = updates[idx];
        if (res.status !== "fulfilled") return j;
        const updated = { ...j, ...res.value };
        if (updated.status === "done") anyDone = true;
        return updated;
      }));
      if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
      if (anyDone) onJobDone();
    }, 1500);
    return () => clearInterval(iv);
  }, [jobs.map(j => j.id + j.status).join(",")]);

  const activeJob = jobs.find(j => j.id === activeJobId) ?? null;
  const steps = ["Descargando", "Transcribiendo", "Analizando", "Cortando clips"];
  const currentStep = activeJob ? stepFromLogs(activeJob.logs) : -1;
  const hasRunning = jobs.some(j => j.status === "queued" || j.status === "running");

  return (
    <div className="space-y-5">
      {/* URL input + queue builder */}
      <div className="glass grad-border rounded-2xl p-4 space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Play size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input
              id="process-url-input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== "Enter") return;
                if (pendingUrls.length === 0) { const u = url.trim(); setUrl(""); submitUrls([u]); }
                else addUrl();
              }}
              placeholder="https://youtu.be/..."
              className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-red-500/40 transition"
            />
          </div>
          <button onClick={addUrl} disabled={!url.trim()}
            className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-300 rounded-xl px-4 py-2.5 text-sm font-medium transition-all">
            + Añadir
          </button>
          {pendingUrls.length > 0 && (
            <button onClick={processQueue} disabled={submitting}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-all hover:shadow-[0_0_20px_rgba(239,68,68,0.35)] hover:scale-105 active:scale-95">
              {submitting ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
              Procesar {pendingUrls.length > 1 ? `${pendingUrls.length} videos` : "video"}
            </button>
          )}
          {pendingUrls.length === 0 && url.trim() && (
            <button onClick={() => { const u = url.trim(); setUrl(""); submitUrls([u]); }}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-all hover:shadow-[0_0_20px_rgba(239,68,68,0.35)] hover:scale-105 active:scale-95">
              <Zap size={13} /> Generar clips
            </button>
          )}
        </div>

        {/* pending queue list */}
        <AnimatePresence>
          {pendingUrls.length > 0 && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
              className="space-y-1.5 border-t border-white/[0.05] pt-3">
              <p className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2">Cola — {pendingUrls.length} URL{pendingUrls.length > 1 ? "s" : ""}</p>
              {pendingUrls.map((u, i) => (
                <motion.div key={u} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-2 bg-zinc-900/50 rounded-lg px-3 py-2">
                  <span className="text-zinc-700 text-xs font-mono w-4 shrink-0">{i + 1}</span>
                  <span className="text-xs text-zinc-400 flex-1 truncate">{urlLabel(u)}</span>
                  <button onClick={() => removeUrl(u)} className="text-zinc-700 hover:text-zinc-400 transition-colors text-xs px-1">×</button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* options row */}
        <div className="flex items-center gap-4 flex-wrap pt-1 border-t border-white/[0.04]">
          <button onClick={() => setFaceTrack(v => !v)}
            className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-all ${faceTrack ? "bg-red-500/10 border-red-500/30 text-red-400" : "bg-zinc-900/40 border-zinc-800 text-zinc-600"}`}>
            <span className={`w-2 h-2 rounded-full ${faceTrack ? "bg-red-500" : "bg-zinc-700"}`} />
            Face tracking
          </button>
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-zinc-600">Captions:</span>
            {(["capcut", "subtitles", "none"] as const).map(s => (
              <button key={s} onClick={() => setCaptionStyle(s)}
                className={`px-2.5 py-1 rounded-lg border transition-all ${captionStyle === s ? "bg-zinc-800 border-zinc-600 text-zinc-200" : "border-zinc-800 text-zinc-600 hover:text-zinc-400"}`}>
                {s === "capcut" ? "CapCut" : s === "subtitles" ? "Subtítulos" : "Ninguno"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-red-400/80 text-sm bg-red-500/5 border border-red-500/10 rounded-xl px-4 py-3">{error}</p>}

      {/* active jobs list */}
      <AnimatePresence>
        {jobs.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">

            {/* jobs switcher */}
            {jobs.length > 1 && (
              <div className="flex flex-wrap gap-2">
                {jobs.map(j => (
                  <button key={j.id} onClick={() => setActiveJobId(j.id)}
                    className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-all ${activeJobId === j.id ? "bg-zinc-800 border-zinc-600 text-zinc-200" : "border-zinc-800 text-zinc-600 hover:text-zinc-400"}`}>
                    <JobStatusDot status={j.status} />
                    <span className="truncate max-w-[120px]">{urlLabel(j.url)}</span>
                  </button>
                ))}
              </div>
            )}

            {activeJob && (
              <>
                {/* step indicator */}
                <div className="glass rounded-2xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    {steps.map((s, i) => (
                      <div key={s} className="flex items-center gap-2">
                        <div className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${i < currentStep ? "text-green-400" : i === currentStep ? "text-yellow-400" : "text-zinc-700"}`}>
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${i < currentStep ? "bg-green-500/20 border border-green-500/40" : i === currentStep ? "bg-yellow-500/20 border border-yellow-500/40 animate-pulse" : "bg-zinc-900 border border-zinc-800"}`}>
                            {i < currentStep ? "✓" : i + 1}
                          </span>
                          {s}
                        </div>
                        {i < steps.length - 1 && <div className={`flex-1 h-px mx-1 w-8 transition-colors ${i < currentStep ? "bg-green-500/40" : "bg-zinc-800"}`} />}
                      </div>
                    ))}
                  </div>
                  <div className={`flex items-center gap-2 text-sm ${activeJob.status === "running" || activeJob.status === "queued" ? "text-yellow-400" : activeJob.status === "done" ? "text-green-400" : "text-red-400"}`}>
                    {(activeJob.status === "running" || activeJob.status === "queued") && <Radio size={13} className="animate-pulse" />}
                    {activeJob.status === "running" || activeJob.status === "queued" ? "Procesando..." :
                     activeJob.status === "done" ? `✓ ${activeJob.clips.length} clips generados` :
                     activeJob.error ?? "Error"}
                  </div>
                </div>

                {/* terminal log */}
                <div className="bg-zinc-950 border border-zinc-800/60 rounded-2xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800/60 bg-zinc-900/30">
                    <span className="w-3 h-3 rounded-full bg-red-500/60" /><span className="w-3 h-3 rounded-full bg-yellow-500/60" /><span className="w-3 h-3 rounded-full bg-green-500/60" />
                    <span className="text-xs text-zinc-600 ml-2 font-mono">{activeJob.id} · pipeline.log</span>
                  </div>
                  <div ref={logsRef} className="p-4 h-40 overflow-y-auto font-mono text-xs space-y-1.5">
                    {activeJob.logs.map((l, i) => (
                      <p key={i} className={`flex gap-2 ${l.toLowerCase().includes("error") || l.toLowerCase().includes("omitido") ? "text-red-400" : l.toLowerCase().includes("listo") || l.toLowerCase().includes("completado") ? "text-green-400" : l.toLowerCase().includes("procesando clip") ? "text-yellow-400" : "text-zinc-500"}`}>
                        <span className="text-zinc-700 shrink-0">›</span><span>{l}</span>
                      </p>
                    ))}
                    {(activeJob.status === "queued" || activeJob.status === "running") && <p className="text-zinc-500 animate-pulse">_</p>}
                  </div>
                </div>

                {/* clips grid */}
                {activeJob.clips.length > 0 && (
                  <div>
                    <p className="text-xs text-zinc-600 uppercase tracking-widest font-medium mb-4">{activeJob.clips.length} clips · listos para publicar</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      {activeJob.clips.map((c) => (
                        <motion.div key={c.filename} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                          className="group bg-zinc-900 border border-zinc-800 hover:border-red-500/30 rounded-2xl overflow-hidden transition-all hover:shadow-[0_0_25px_rgba(239,68,68,0.1)]">
                          <div className="relative bg-zinc-950">
                            <video src={api.clipUrl(c.filename)} controls preload="metadata" className="w-full aspect-[9/16] object-cover" />
                            <div className="absolute top-2 right-2">
                              <span className="bg-black/70 backdrop-blur text-xs px-2 py-0.5 rounded-full text-zinc-300">9:16</span>
                            </div>
                          </div>
                          <div className="p-3.5 space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-xs font-semibold line-clamp-1 text-zinc-200">{c.title}</p>
                              <ScoreBadge score={c.score} reason={c.virality_reason} />
                            </div>
                            <p className="text-[11px] text-zinc-600 line-clamp-2 leading-relaxed">{c.hook}</p>
                            <div className="flex items-center gap-2 flex-wrap">
                              <a href={api.clipUrl(c.filename)} download={c.filename}
                                className="flex items-center gap-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1.5 rounded-xl transition-colors font-medium">
                                <Download size={11} /> Descargar
                              </a>
                              <PublishButton filename={c.filename} />
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Clip Card ─────────────────────────────────────────────────────────────────
function ClipCard({ clip: c }: { clip: import("../lib/api").Clip }) {
  const [view, setView] = useState<"video" | "thumb">("video");
  const [thumbLoading, setThumbLoading] = useState(false);
  const [thumbSrc, setThumbSrc] = useState(c.thumbnail ? api.thumbnailUrl(c.thumbnail) : null);

  async function regenThumb() {
    setThumbLoading(true);
    try {
      const res = await api.regenThumbnail(c.filename);
      setThumbSrc(api.thumbnailUrl(res.thumbnail));
      setView("thumb");
    } catch { /* ignore */ }
    finally { setThumbLoading(false); }
  }

  return (
    <motion.div variants={fadeUp}
      className="group bg-zinc-900 border border-zinc-800 hover:border-red-500/30 rounded-2xl overflow-hidden transition-all hover:shadow-[0_0_25px_rgba(239,68,68,0.1)]">
      <div className="relative bg-zinc-950">
        {view === "thumb" && thumbSrc
          ? <img src={thumbSrc} alt={c.title} className="w-full aspect-[9/16] object-cover" />
          : <video src={api.clipUrl(c.filename)} controls preload="metadata" className="w-full aspect-[9/16] object-cover" />
        }
        {/* top-right controls */}
        <div className="absolute top-2 right-2 flex items-center gap-1">
          {thumbSrc && (
            <button onClick={() => setView(v => v === "video" ? "thumb" : "video")}
              className="bg-black/70 backdrop-blur text-[10px] px-2 py-0.5 rounded-full text-zinc-300 hover:text-white transition-colors">
              {view === "video" ? "Thumb" : "Video"}
            </button>
          )}
          <span className="bg-black/70 backdrop-blur text-[10px] px-2 py-0.5 rounded-full text-zinc-400">9:16</span>
        </div>
      </div>
      <div className="p-3 space-y-1.5">
        <div className="flex items-start justify-between gap-1.5">
          {c.title && <p className="text-xs font-semibold text-zinc-200 line-clamp-1 flex-1">{c.title}</p>}
          <ScoreBadge score={c.score} reason={c.virality_reason} />
        </div>
        {c.virality_reason && (
          <p className="text-[10px] text-zinc-600 line-clamp-1 italic">{c.virality_reason}</p>
        )}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-xs text-zinc-600">{c.size_mb} MB</span>
          <div className="flex items-center gap-2 flex-wrap">
            <a href={api.clipUrl(c.filename)} download={c.filename}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-200 transition-colors">
              <Download size={11} /> Clip
            </a>
            {thumbSrc && (
              <a href={thumbSrc} download={c.thumbnail}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-200 transition-colors">
                <Download size={11} /> Thumb
              </a>
            )}
            {!thumbSrc && (
              <button onClick={regenThumb} disabled={thumbLoading}
                className="flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-300 transition-colors disabled:opacity-40">
                {thumbLoading ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
                Thumb
              </button>
            )}
            <PublishButton filename={c.filename} />
          </div>
          <ScheduleButton filename={c.filename} />
        </div>
      </div>
    </motion.div>
  );
}

// ── Clips ─────────────────────────────────────────────────────────────────────
function ClipsSection({ refreshKey }: { refreshKey: number }) {
  const [clips, setClips] = useState<import("../lib/api").Clip[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await api.listClips(); setClips(r.clips); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading) return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      {[...Array(8)].map((_, i) => <div key={i} className="shimmer rounded-2xl aspect-[9/16]" style={{ animationDelay: `${i * 80}ms` }} />)}
    </div>
  );

  if (!clips.length) return (
    <div className="glass rounded-2xl py-20 text-center border-dashed">
      <VideoIcon size={36} className="mx-auto mb-4 text-zinc-700" />
      <p className="text-zinc-500 font-medium mb-1">Sin clips aún</p>
      <p className="text-zinc-700 text-sm">Procesa un video para ver tus clips aquí</p>
    </div>
  );

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      {clips.map((c) => (
        <ClipCard key={c.filename} clip={c} />
      ))}
    </motion.div>
  );
}

// ── Analytics ─────────────────────────────────────────────────────────────────
type Report = {
  id: string; title: string; url: string; published: string;
  views: number; retention_pct: number; avg_view_duration_s: number;
  watch_minutes: number; likes: number; shares: number; subs_gained: number;
};

function SparkBar({ value, max }: { value: number; max: number }) {
  return (
    <div className="flex items-end gap-0.5 h-5">
      {[...Array(5)].map((_, i) => {
        const threshold = (i + 1) / 5;
        const filled = value / max >= threshold;
        return <span key={i} className={`w-1.5 rounded-sm transition-colors ${filled ? "bg-red-500" : "bg-zinc-800"}`}
          style={{ height: `${30 + i * 15}%` }} />;
      })}
    </div>
  );
}

function AnalyticsSection() {
  const [days, setDays] = useState(28);
  const [report, setReport] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [insights, setInsights] = useState<string[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);

  const load = useCallback(async (d: number) => {
    setLoading(true);
    setError("");
    setInsights([]);
    try { const res = await api.analytics(d); setReport(res.report as Report[]); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
    finally { setLoading(false); }
  }, []);

  async function loadInsights() {
    setInsightsLoading(true);
    try { const res = await api.analyticsInsights(days); setInsights(res.insights); }
    catch (e: unknown) { setInsights([e instanceof Error ? e.message : "Error generando insights"]); }
    finally { setInsightsLoading(false); }
  }

  useEffect(() => { load(28); }, []);

  const best = report[0];
  const maxViews = Math.max(...report.map((r) => r.views), 1);

  return (
    <div className="space-y-6">
      {/* period selector + insights button */}
      <div className="flex items-center gap-2 flex-wrap">
        {[7, 28, 90].map((d) => (
          <button key={d} onClick={() => { setDays(d); load(d); }}
            className={`text-sm px-4 py-2 rounded-xl border transition-all ${
              days === d
                ? "bg-zinc-800 border-zinc-600 text-zinc-100 shadow-[0_0_15px_rgba(255,255,255,0.05)]"
                : "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400"
            }`}>
            {d} días
          </button>
        ))}
        {loading && <Loader2 size={13} className="animate-spin text-zinc-600 ml-2" />}
        {report.length > 0 && (
          <button onClick={loadInsights} disabled={insightsLoading}
            className="ml-auto flex items-center gap-2 text-sm px-4 py-2 rounded-xl border border-red-500/30 bg-red-500/5 hover:bg-red-500/10 text-red-400 disabled:opacity-40 transition-all">
            {insightsLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
            {insightsLoading ? "Analizando..." : "Insights IA"}
          </button>
        )}
      </div>

      {/* AI Insights panel */}
      <AnimatePresence>
        {insights.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
            className="glass grad-border rounded-2xl p-5 space-y-3">
            <p className="text-xs text-red-400/80 font-medium uppercase tracking-widest flex items-center gap-1.5">
              <Sparkles size={10} /> Insights IA · últimos {days} días
            </p>
            <ul className="space-y-2">
              {insights.map((ins, i) => (
                <motion.li key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }}
                  className="flex items-start gap-3 text-sm text-zinc-300 leading-relaxed">
                  <span className="text-base shrink-0">{ins.match(/^\p{Emoji}/u)?.[0] ?? "•"}</span>
                  <span>{ins.replace(/^\p{Emoji}\s*/u, "")}</span>
                </motion.li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <div className="glass rounded-2xl p-6 text-center space-y-2">
          <p className="text-zinc-400 text-sm">{error}</p>
          <p className="text-zinc-600 text-xs">Conecta YouTube OAuth: <code className="bg-zinc-900 px-1.5 py-0.5 rounded text-zinc-500">python scripts/setup_youtube.py</code></p>
        </div>
      )}

      {best && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden glass grad-border rounded-2xl p-6">
          <div className="absolute top-0 right-0 w-48 h-48 bg-red-600/5 rounded-full blur-2xl pointer-events-none" />
          <div className="flex items-start justify-between gap-4 mb-5 relative">
            <div>
              <p className="text-xs text-red-400/80 font-medium uppercase tracking-widest flex items-center gap-1.5 mb-2">
                <TrendingUp size={10} /> Mejor clip · últimos {days} días
              </p>
              <a href={best.url} target="_blank" rel="noopener noreferrer"
                className="font-semibold text-base hover:text-red-400 transition-colors line-clamp-1 max-w-md block">
                {best.title}
              </a>
              <p className="text-xs text-zinc-600 mt-1">{best.published}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-5 relative">
            {[
              { val: `${best.retention_pct}%`, label: "Retención media", color: "text-red-400" },
              { val: fmt(best.views),           label: "Vistas totales",  color: "text-zinc-100" },
              { val: fmtDur(best.avg_view_duration_s), label: "Dur. promedio", color: "text-violet-400" },
              { val: `+${best.subs_gained}`,    label: "Subs ganados",    color: "text-green-400" },
            ].map(({ val, label, color }) => (
              <div key={label} className="bg-zinc-900/60 rounded-xl p-3.5">
                <p className={`text-2xl font-bold tabular-nums ${color}`}>{val}</p>
                <p className="text-xs text-zinc-600 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {report.length > 0 && (
        <div className="glass rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-600 border-b border-white/[0.04]">
                <th className="text-left py-3.5 px-5">Video</th>
                <th className="text-right py-3.5 px-3">Retención</th>
                <th className="text-right py-3.5 px-3"><span className="flex items-center gap-1 justify-end"><Eye size={10}/>Vistas</span></th>
                <th className="text-right py-3.5 px-3 hidden sm:table-cell">Dur. avg</th>
                <th className="text-right py-3.5 px-3 hidden sm:table-cell"><span className="flex items-center gap-1 justify-end"><ThumbsUp size={10}/>Likes</span></th>
                <th className="text-right py-3.5 px-5">Subs</th>
              </tr>
            </thead>
            <tbody>
              {report.map((r, i) => (
                <motion.tr key={r.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}
                  className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                  <td className="py-3.5 px-5">
                    <a href={r.url} target="_blank" rel="noopener noreferrer"
                      className="hover:text-red-400 transition-colors text-zinc-300 line-clamp-1 block max-w-xs text-xs font-medium">
                      {r.title}
                    </a>
                    <p className="text-[10px] text-zinc-700 mt-0.5">{r.published}</p>
                  </td>
                  <td className="text-right py-3.5 px-3">
                    <span className={`font-bold text-xs tabular-nums ${r.retention_pct >= 50 ? "text-green-400" : r.retention_pct >= 30 ? "text-yellow-400" : "text-zinc-500"}`}>
                      {r.retention_pct}%
                    </span>
                  </td>
                  <td className="text-right py-3.5 px-3">
                    <div className="flex items-center justify-end gap-2">
                      <SparkBar value={r.views} max={maxViews} />
                      <span className="text-xs text-zinc-400 tabular-nums">{fmt(r.views)}</span>
                    </div>
                  </td>
                  <td className="text-right py-3.5 px-3 text-xs text-zinc-600 hidden sm:table-cell tabular-nums">{fmtDur(r.avg_view_duration_s)}</td>
                  <td className="text-right py-3.5 px-3 text-xs text-zinc-600 hidden sm:table-cell tabular-nums">{r.likes.toLocaleString()}</td>
                  <td className="text-right py-3.5 px-5 text-xs text-zinc-500 tabular-nums">+{r.subs_gained}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
