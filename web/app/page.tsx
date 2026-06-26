"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { api, type Video, type Job, type ProfileItem, type StyleItem } from "@/lib/api";
import {
  Search, Zap, Video as VideoIcon, BarChart2, TrendingUp,
  Download, ChevronDown, Clock, Eye, ThumbsUp, Play, Loader2,
  ArrowRight, Sparkles, Radio, ChevronRight, Upload, ExternalLink,
  CalendarClock, CheckCircle2, XCircle, Trash2, LayoutGrid, Copy,
  ChevronLeft, ImageIcon, Scissors, X, Palette, Check, Pencil,
} from "lucide-react";

// ── Slide lightbox ─────────────────────────────────────────────────────────────
function SlideModal({
  images, slug, current, total, onClose, onGoto,
}: {
  images: string[]; slug: string; current: number; total: number;
  onClose: () => void; onGoto: (i: number) => void;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft")  onGoto(Math.max(0, current - 1));
      if (e.key === "ArrowRight") onGoto(Math.min(images.length - 1, current + 1));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [current, images.length, onClose, onGoto]);

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="fixed inset-0 z-50 bg-black/96 backdrop-blur-sm flex items-center justify-center"
      onClick={onClose}
    >
      {/* Counter */}
      <div className="absolute top-5 left-1/2 -translate-x-1/2 text-zinc-400 text-sm font-mono tabular-nums select-none">
        {current + 1} / {total}
      </div>

      {/* Close */}
      <button onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-full bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition-all z-10">
        <X className="w-5 h-5" />
      </button>

      {/* Image */}
      <motion.div
        key={current}
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.15 }}
        className="relative h-[90vh] aspect-[4/5] rounded-2xl overflow-hidden shadow-2xl ring-1 ring-white/10"
        onClick={e => e.stopPropagation()}
      >
        <img
          src={api.slideImageUrl(slug, images[current])}
          alt={`Slide ${current + 1}`}
          className="w-full h-full object-cover"
        />
      </motion.div>

      {/* Prev */}
      {current > 0 && (
        <button
          onClick={e => { e.stopPropagation(); onGoto(current - 1); }}
          className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white transition-all">
          <ChevronLeft className="w-6 h-6" />
        </button>
      )}
      {/* Next */}
      {current < images.length - 1 && (
        <button
          onClick={e => { e.stopPropagation(); onGoto(current + 1); }}
          className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white transition-all">
          <ChevronRight className="w-6 h-6" />
        </button>
      )}

      {/* Dot nav */}
      <div className="absolute bottom-5 left-1/2 -translate-x-1/2 flex gap-1.5" onClick={e => e.stopPropagation()}>
        {images.map((_, i) => (
          <button key={i} onClick={() => onGoto(i)}
            className={`rounded-full transition-all ${i === current ? "w-5 h-1.5 bg-white" : "w-1.5 h-1.5 bg-white/35 hover:bg-white/60"}`} />
        ))}
      </div>
    </motion.div>
  );
}

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

// ── nav per mode ──────────────────────────────────────────────────────────────
const CLIPS_NAV = [
  { id: "discover",  label: "Descubrir",  Icon: Search },
  { id: "process",   label: "Procesar",   Icon: Zap },
  { id: "clips",     label: "Mis clips",  Icon: VideoIcon },
  { id: "analytics", label: "Analytics",  Icon: BarChart2 },
];
const SLIDES_NAV = [
  { id: "slides-gen",  label: "Generar",   Icon: Sparkles },
  { id: "slides-hist", label: "Historial", Icon: LayoutGrid },
];

const CLIPS_SUGGESTIONS = [
  "historia curiosidades", "gaming reacción", "ciencia sorprendente",
  "misterios inexplicables", "finanzas personales", "true crime español",
];

// ── root ──────────────────────────────────────────────────────────────────────
type Mode = "clips" | "slides";

export default function App() {
  const [mode, setMode]         = useState<Mode>("clips");
  const [active, setActive]     = useState("discover");
  const [processUrl, setProcessUrl] = useState("");
  const [clipsVersion, setClipsVersion] = useState(0);

  const NAV = mode === "clips" ? CLIPS_NAV : SLIDES_NAV;

  // Re-attach IntersectionObserver when mode changes
  useEffect(() => {
    setActive(NAV[0].id);
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id); }),
      { rootMargin: "-35% 0px -55% 0px" },
    );
    NAV.forEach(({ id }) => { const el = document.getElementById(id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, [mode]);

  function go(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function switchMode(m: Mode) {
    setMode(m);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleSelectVideo(url: string) {
    setProcessUrl(url);
    setTimeout(() => go("process"), 50);
  }

  // Accent colors per mode
  const accent = mode === "clips"
    ? { pill: "bg-red-600",     text: "text-red-400",     ring: "ring-red-500/40",     glow: "hover:shadow-[0_0_20px_rgba(239,68,68,0.35)]",   border: "border-red-500/20",  blob1: "bg-red-600/10",   blob2: "bg-violet-600/8",  badge: "bg-red-500/10 border-red-500/15", badgeText: "text-red-400" }
    : { pill: "bg-emerald-600", text: "text-emerald-400", ring: "ring-emerald-500/40", glow: "hover:shadow-[0_0_20px_rgba(16,185,129,0.35)]",   border: "border-emerald-500/20", blob1: "bg-emerald-600/10", blob2: "bg-teal-600/8", badge: "bg-emerald-500/10 border-emerald-500/15", badgeText: "text-emerald-400" };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">

      {/* ── sticky nav ───────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 px-6 py-3 flex items-center gap-4 border-b border-white/[0.05] backdrop-blur-2xl bg-zinc-950/75">
        <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="text-lg font-bold tracking-tight shrink-0 select-none">
          <span className="grad-text">You</span><span>AI3</span>
        </button>

        {/* ── mode switcher ── */}
        <div className="flex items-center gap-0.5 bg-zinc-900 border border-zinc-800 rounded-xl p-1 shrink-0">
          <button
            onClick={() => switchMode("clips")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
              mode === "clips" ? "bg-red-600 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Scissors size={11} /> Clips
          </button>
          <button
            onClick={() => switchMode("slides")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
              mode === "slides" ? "bg-emerald-600 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <ImageIcon size={11} /> Contenido
          </button>
        </div>

        {/* ── section nav ── */}
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

      <AnimatePresence mode="wait">
        {/* ═══════════════════════════════════════════════════════════════════
            CLIPS MODE
        ═══════════════════════════════════════════════════════════════════ */}
        {mode === "clips" && (
          <motion.div key="clips" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
            {/* ── hero ── */}
            <section className="relative min-h-[88vh] flex flex-col items-center justify-center text-center px-6 overflow-hidden">
              <div className="absolute -top-32 -left-32 w-96 h-96 bg-red-600/10 rounded-full blur-3xl pointer-events-none"
                style={{ animation: "float 8s ease-in-out infinite" }} />
              <div className="absolute -bottom-20 -right-20 w-80 h-80 bg-violet-600/8 rounded-full blur-3xl pointer-events-none"
                style={{ animation: "float 10s ease-in-out infinite reverse" }} />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-red-900/5 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute inset-0 opacity-[0.025] pointer-events-none"
                style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)", backgroundSize: "64px 64px" }} />

              <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }} className="w-full max-w-2xl">
                <div className="inline-flex items-center gap-2 glass border border-red-500/20 text-red-400 text-xs px-4 py-2 rounded-full mb-8">
                  <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
                  <Scissors size={11} />
                  Creador de Clips · YouTube Shorts automáticos
                </div>
                <h1 className="text-6xl sm:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
                  Convierte videos en<br />
                  <span className="grad-text">clips virales</span>
                </h1>
                <p className="text-zinc-400 max-w-lg mx-auto mb-8 text-lg leading-relaxed">
                  Pega un link de YouTube, la IA encuentra los momentos virales y genera Shorts en 9:16 listos para publicar.
                </p>
                <div className="flex items-center justify-center gap-4">
                  <button onClick={() => go("process")}
                    className="group flex items-center gap-2.5 bg-red-600 hover:bg-red-500 text-white font-semibold px-7 py-3.5 rounded-2xl transition-all duration-200 hover:scale-105 hover:shadow-[0_0_30px_rgba(239,68,68,0.4)]">
                    Generar clips <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
                  </button>
                  <button onClick={() => go("discover")}
                    className="flex items-center gap-2 glass glass-hover text-zinc-300 px-6 py-3.5 rounded-2xl transition-all text-sm font-medium">
                    <Search size={14} className="text-red-400" /> Buscar outliers
                  </button>
                </div>
              </motion.div>

              <motion.div initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5, duration: 0.6 }}
                className="absolute right-8 top-1/2 -translate-y-1/2 hidden xl:flex flex-col gap-3">
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

            {/* ── clips sections ── */}
            <div className="max-w-5xl mx-auto px-6 pb-32 space-y-28">
              <section id="discover" className="scroll-mt-20">
                <SectionLabel Icon={Search} label="Descubrir" accent="text-red-400" iconBg="bg-red-500/10 border-red-500/20" iconGlow="bg-red-500/20" />
                <DiscoverSection onSelectVideo={handleSelectVideo} />
              </section>
              <WaveDivider />
              <section id="process" className="scroll-mt-20">
                <SectionLabel Icon={Zap} label="Procesar video" accent="text-red-400" iconBg="bg-red-500/10 border-red-500/20" iconGlow="bg-red-500/20" />
                <ProcessSection url={processUrl} setUrl={setProcessUrl} onJobDone={() => setClipsVersion((v) => v + 1)} />
              </section>
              <WaveDivider />
              <section id="clips" className="scroll-mt-20">
                <SectionLabel Icon={VideoIcon} label="Mis clips" accent="text-red-400" iconBg="bg-red-500/10 border-red-500/20" iconGlow="bg-red-500/20" />
                <ClipsSection refreshKey={clipsVersion} />
              </section>
              <WaveDivider />
              <section id="schedule" className="scroll-mt-20">
                <SectionLabel Icon={CalendarClock} label="Programados" accent="text-red-400" iconBg="bg-red-500/10 border-red-500/20" iconGlow="bg-red-500/20" />
                <ScheduleSection />
              </section>
              <WaveDivider />
              <section id="analytics" className="scroll-mt-20">
                <SectionLabel Icon={BarChart2} label="Analytics" accent="text-red-400" iconBg="bg-red-500/10 border-red-500/20" iconGlow="bg-red-500/20" />
                <AnalyticsSection />
              </section>
            </div>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            SLIDES / CONTENT MODE
        ═══════════════════════════════════════════════════════════════════ */}
        {mode === "slides" && (
          <motion.div key="slides" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
            {/* ── slides hero ── */}
            <section className="relative min-h-[88vh] flex flex-col items-center justify-center text-center px-6 overflow-hidden">
              <div className="absolute -top-32 -left-32 w-96 h-96 bg-emerald-600/10 rounded-full blur-3xl pointer-events-none"
                style={{ animation: "float 8s ease-in-out infinite" }} />
              <div className="absolute -bottom-20 -right-20 w-80 h-80 bg-teal-600/8 rounded-full blur-3xl pointer-events-none"
                style={{ animation: "float 10s ease-in-out infinite reverse" }} />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-emerald-900/5 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute inset-0 opacity-[0.025] pointer-events-none"
                style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)", backgroundSize: "64px 64px" }} />

              <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }} className="w-full max-w-2xl">
                <div className="inline-flex items-center gap-2 glass border border-emerald-500/20 text-emerald-400 text-xs px-4 py-2 rounded-full mb-8">
                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                  <ImageIcon size={11} />
                  Creador de Contenido · Slides para Instagram y Reels
                </div>
                <h1 className="text-6xl sm:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
                  Slides educativos<br />
                  <span style={{ background: "linear-gradient(135deg, #10b981, #14b8a6, #06b6d4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                    listos para postear
                  </span>
                </h1>
                <p className="text-zinc-400 max-w-lg mx-auto mb-8 text-lg leading-relaxed">
                  Escribe un tema de plantas o naturaleza. Gemini genera el contenido, busca las mejores fotos y arma el carrusel con narración.
                </p>
                <div className="flex items-center justify-center gap-4">
                  <button onClick={() => go("slides-gen")}
                    className="group flex items-center gap-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-7 py-3.5 rounded-2xl transition-all duration-200 hover:scale-105 hover:shadow-[0_0_30px_rgba(16,185,129,0.4)]">
                    Crear carrusel <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
                  </button>
                  <button onClick={() => go("slides-hist")}
                    className="flex items-center gap-2 glass glass-hover text-zinc-300 px-6 py-3.5 rounded-2xl transition-all text-sm font-medium">
                    <LayoutGrid size={14} className="text-emerald-400" /> Ver historial
                  </button>
                </div>
              </motion.div>

              <motion.div initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5, duration: 0.6 }}
                className="absolute right-8 top-1/2 -translate-y-1/2 hidden xl:flex flex-col gap-3">
                {[
                  { label: "Slides/carrusel", val: "10",    color: "text-emerald-400" },
                  { label: "Estilos",          val: "4",     color: "text-teal-400" },
                  { label: "Con narración",    val: "45s",   color: "text-cyan-400" },
                ].map(({ label, val, color }) => (
                  <div key={label} className="glass border border-emerald-500/10 rounded-xl px-4 py-3 text-right">
                    <p className={`text-xl font-bold ${color}`}>{val}</p>
                    <p className="text-xs text-zinc-600">{label}</p>
                  </div>
                ))}
              </motion.div>

              <button onClick={() => go("slides-gen")} className="absolute bottom-8 left-1/2 -translate-x-1/2 text-zinc-700 hover:text-zinc-500 transition-colors animate-bounce">
                <ChevronDown size={22} />
              </button>
            </section>

            {/* ── slides studio ── */}
            <div className="max-w-6xl mx-auto px-4 pb-20">
              <SlidesCreatorStudio />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Shared UI primitives ──────────────────────────────────────────────────────
function SectionLabel({ Icon, label, accent, iconBg, iconGlow }: {
  Icon: React.ElementType; label: string;
  accent: string; iconBg: string; iconGlow: string;
}) {
  return (
    <div className="flex items-center gap-3 mb-8">
      <div className="relative">
        <div className={`absolute inset-0 ${iconGlow} rounded-xl blur-sm opacity-60`} />
        <div className={`relative ${iconBg} border p-2.5 rounded-xl`}>
          <Icon size={16} className={accent} />
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
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent blur-sm" />
    </div>
  );
}

// ── Schedule ──────────────────────────────────────────────────────────────────
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

  useEffect(() => {
    if (!jobs.some(j => j.status === "pending" || j.status === "running")) return;
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, [jobs.map(j => j.id + j.status).join(",")]);

  function fmtDate(iso: string) {
    try { return new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(iso)); }
    catch { return iso; }
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
          {j.status === "done"      ? <CheckCircle2 size={16} className="text-green-400 shrink-0" />
           : j.status === "error"   ? <XCircle size={16} className="text-red-400 shrink-0" />
           : j.status === "running" ? <Loader2 size={16} className="text-yellow-400 animate-spin shrink-0" />
           : j.status === "cancelled" ? <XCircle size={16} className="text-zinc-600 shrink-0" />
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
            j.status === "done"      ? "bg-green-500/10 border-green-500/20 text-green-400" :
            j.status === "error"     ? "bg-red-500/10 border-red-500/20 text-red-400" :
            j.status === "running"   ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-400" :
            j.status === "cancelled" ? "bg-zinc-800 border-zinc-700 text-zinc-600" :
                                       "bg-zinc-800 border-zinc-700 text-zinc-400"
          }`}>{j.status}</span>
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

  function openPicker() {
    const d = new Date(Date.now() + 24 * 3600 * 1000);
    d.setSeconds(0, 0);
    setDt(d.toISOString().slice(0, 16));
    setState("idle"); setMsg(""); setOpen(true);
  }

  async function submit() {
    if (!dt) return;
    setState("loading");
    try {
      await api.scheduleClip(filename, dt + ":00");
      setState("done"); setMsg("Programado");
      setTimeout(() => setOpen(false), 1500);
    } catch (e: unknown) {
      setState("error");
      setMsg(e instanceof Error ? e.message.slice(0, 60) : "Error");
    }
  }

  if (!open) return (
    <button onClick={openPicker} className="flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-300 transition-colors">
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

const PLATFORM_META = {
  youtube:   { label: "YouTube", color: "hover:bg-red-600 hover:border-red-500 hover:text-white",   doneColor: "bg-red-600/20 text-red-400 border-red-500/30" },
  tiktok:    { label: "TikTok",  color: "hover:bg-black hover:border-zinc-500 hover:text-white",     doneColor: "bg-zinc-800 text-zinc-300 border-zinc-600" },
  instagram: { label: "IG Reel", color: "hover:bg-pink-600 hover:border-pink-500 hover:text-white",  doneColor: "bg-pink-600/20 text-pink-400 border-pink-500/30" },
} as const;

type PlatformId = keyof typeof PLATFORM_META;

function PlatformButtons({ filename, published: initialPublished }: {
  filename: string;
  published?: Record<string, string>;
}) {
  const [platforms, setPlatforms] = useState<Record<string, { configured: boolean; hint: string }>>({});
  const [states, setStates] = useState<Record<string, "idle" | "loading" | "done" | "error">>({});
  const [urls, setUrls] = useState<Record<string, string>>(initialPublished ?? {});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => { api.getPlatforms().then(p => setPlatforms(p)).catch(() => {}); }, []);

  async function publish(platform: PlatformId) {
    setStates(s => ({ ...s, [platform]: "loading" }));
    try {
      const res = await api.publishClip(filename, platform);
      setUrls(u => ({ ...u, [platform]: res.url }));
      setStates(s => ({ ...s, [platform]: "done" }));
    } catch (e: unknown) {
      setErrors(er => ({ ...er, [platform]: e instanceof Error ? e.message : "Error" }));
      setStates(s => ({ ...s, [platform]: "error" }));
    }
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(PLATFORM_META) as PlatformId[]).map(p => {
        const meta = PLATFORM_META[p];
        const cfg = platforms[p];
        const st = states[p] ?? "idle";
        const publishedUrl = urls[p];

        if (publishedUrl || st === "done") return (
          <a key={p} href={publishedUrl} target="_blank" rel="noreferrer"
            className={`flex items-center gap-1 text-[11px] border px-2.5 py-1 rounded-lg transition-colors ${meta.doneColor}`}>
            <CheckCircle2 size={9} /> {meta.label}
          </a>
        );

        const notConfigured = cfg && !cfg.configured;
        return (
          <button key={p} onClick={() => publish(p)}
            disabled={st === "loading" || notConfigured}
            title={notConfigured ? cfg.hint : `Publicar en ${meta.label}`}
            className={`flex items-center gap-1 text-[11px] bg-zinc-800 border border-zinc-700 text-zinc-500 px-2.5 py-1 rounded-lg transition-all
              ${notConfigured ? "opacity-30 cursor-not-allowed" : meta.color}`}>
            {st === "loading" ? <Loader2 size={9} className="animate-spin" />
             : st === "error"  ? <XCircle size={9} className="text-red-400" />
             : <Upload size={9} />}
            {meta.label}
          </button>
        );
      })}
    </div>
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
    setQuery(q); setLoading(true); setError(""); setVideos([]);
    try {
      const res = await api.research(q, { ratio, cc });
      setVideos(res.videos);
      if (!res.videos.length) setError("No se encontraron outliers. Prueba reducir el ratio.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al buscar");
    } finally { setLoading(false); }
  }

  const maxRatio = Math.max(...videos.map((v) => v.outlier_ratio), 1);

  return (
    <div className="space-y-5">
      <div className="glass grad-border rounded-2xl p-4 flex gap-3 flex-wrap items-center">
        <div className="flex-1 min-w-60 relative">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder='Ej: "historia curiosidades", "gaming reacción"'
            className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-red-500/40 focus:border-red-500/40 transition" />
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

      <div className="flex gap-2 flex-wrap">
        {CLIPS_SUGGESTIONS.map((s) => (
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
          {[...Array(5)].map((_, i) => <div key={i} className="shimmer h-20 rounded-2xl" style={{ opacity: 1 - i * 0.15 }} />)}
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
  id: string; url: string; status: string; logs: string[];
  clips: { filename: string; title: string; hook: string; score?: number; virality_reason?: string; published?: Record<string, string> }[];
  error?: string;
};

function urlLabel(u: string) {
  try {
    const parts = new URL(u).hostname.replace("www.", "") + new URL(u).pathname;
    return parts.length > 40 ? parts.slice(0, 40) + "…" : parts;
  } catch { return u.length > 50 ? u.slice(0, 50) + "…" : u; }
}

function JobStatusDot({ status }: { status: string }) {
  if (status === "done")    return <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />;
  if (status === "error")   return <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />;
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

function ProcessSection({ url, setUrl, onJobDone }: {
  url: string; setUrl: (u: string) => void; onJobDone: () => void;
}) {
  const [pendingUrls, setPendingUrls] = useState<string[]>([]);
  const [jobs, setJobs] = useState<ActiveJob[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [captionStyle, setCaptionStyle] = useState<"capcut" | "karaoke" | "subtitles" | "none">("capcut");
  const [faceTrack, setFaceTrack] = useState(true);
  const logsRef = useRef<HTMLDivElement>(null);

  function addUrl() {
    const u = url.trim();
    if (!u || pendingUrls.includes(u)) return;
    setPendingUrls(prev => [...prev, u]); setUrl("");
  }
  function removeUrl(u: string) { setPendingUrls(prev => prev.filter(x => x !== u)); }

  async function submitUrls(urls: string[]) {
    if (!urls.length) return;
    setSubmitting(true); setError("");
    try {
      const res = await api.createQueue(urls, { captionStyle, faceTrack });
      const newJobs: ActiveJob[] = res.job_ids.map((id, i) => ({ id, url: urls[i], status: "queued", logs: [], clips: [] }));
      setJobs(prev => [...newJobs, ...prev]);
      setActiveJobId(res.job_ids[0]);
      setPendingUrls([]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al iniciar la cola");
      setSubmitting(false);
    }
  }

  useEffect(() => {
    const activeIds = jobs.filter(j => j.status === "queued" || j.status === "running").map(j => j.id);
    if (!activeIds.length) { setSubmitting(false); return; }
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

  return (
    <div className="space-y-5">
      <div className="glass grad-border rounded-2xl p-4 space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Play size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input id="process-url-input" value={url} onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== "Enter") return;
                if (pendingUrls.length === 0) { const u = url.trim(); setUrl(""); submitUrls([u]); }
                else addUrl();
              }}
              placeholder="https://youtu.be/..."
              className="w-full bg-zinc-900/60 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-red-500/40 transition" />
          </div>
          <button onClick={addUrl} disabled={!url.trim()}
            className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-300 rounded-xl px-4 py-2.5 text-sm font-medium transition-all">
            + Añadir
          </button>
          {pendingUrls.length > 0 && (
            <button onClick={() => submitUrls(pendingUrls)} disabled={submitting}
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

        <div className="flex items-center gap-4 flex-wrap pt-1 border-t border-white/[0.04]">
          <button onClick={() => setFaceTrack(v => !v)}
            className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-all ${faceTrack ? "bg-red-500/10 border-red-500/30 text-red-400" : "bg-zinc-900/40 border-zinc-800 text-zinc-600"}`}>
            <span className={`w-2 h-2 rounded-full ${faceTrack ? "bg-red-500" : "bg-zinc-700"}`} />
            Face tracking
          </button>
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-zinc-600">Captions:</span>
            {(["capcut", "karaoke", "subtitles", "none"] as const).map(s => (
              <button key={s} onClick={() => setCaptionStyle(s)}
                className={`px-2.5 py-1 rounded-lg border transition-all ${captionStyle === s ? "bg-zinc-800 border-zinc-600 text-zinc-200" : "border-zinc-800 text-zinc-600 hover:text-zinc-400"}`}>
                {s === "capcut" ? "CapCut" : s === "karaoke" ? "Karaoke" : s === "subtitles" ? "Subtítulos" : "Ninguno"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-red-400/80 text-sm bg-red-500/5 border border-red-500/10 rounded-xl px-4 py-3">{error}</p>}

      <AnimatePresence>
        {jobs.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
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
                    {activeJob.status === "running" || activeJob.status === "queued" ? "Procesando..."
                     : activeJob.status === "done" ? `✓ ${activeJob.clips.length} clips generados`
                     : activeJob.error ?? "Error"}
                  </div>
                </div>

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
                              <PlatformButtons filename={c.filename} published={c.published} />
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
    try { const res = await api.regenThumbnail(c.filename); setThumbSrc(api.thumbnailUrl(res.thumbnail)); setView("thumb"); }
    catch { /* ignore */ }
    finally { setThumbLoading(false); }
  }

  return (
    <motion.div variants={fadeUp}
      className="group bg-zinc-900 border border-zinc-800 hover:border-red-500/30 rounded-2xl overflow-hidden transition-all hover:shadow-[0_0_25px_rgba(239,68,68,0.1)]">
      <div className="relative bg-zinc-950">
        {view === "thumb" && thumbSrc
          ? <img src={thumbSrc} alt={c.title} className="w-full aspect-[9/16] object-cover" />
          : <video src={api.clipUrl(c.filename)} controls preload="metadata" className="w-full aspect-[9/16] object-cover" />}
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
        {c.virality_reason && <p className="text-[10px] text-zinc-600 line-clamp-1 italic">{c.virality_reason}</p>}
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
                {thumbLoading ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />} Thumb
              </button>
            )}
            <PlatformButtons filename={c.filename} published={c.published} />
          </div>
          <ScheduleButton filename={c.filename} />
        </div>
      </div>
    </motion.div>
  );
}

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
      {clips.map((c) => <ClipCard key={c.filename} clip={c} />)}
    </motion.div>
  );
}

// ── Slides — Generator section ────────────────────────────────────────────────
// Static swatches for built-in styles
const BUILTIN_SWATCHES: Record<string, string> = {
  botanico:    "from-[#040e06] via-[#0a1f0b] to-[#111600]",
  terracota:   "from-[#150300] via-[#280800] to-[#340e00]",
  aesthetic:   "from-[#180912] via-[#261030] to-[#180c25]",
  dark_jungle: "from-[#010301] via-[#020805] to-[#010602]",
  sage:        "from-[#060e04] via-[#112810] to-[#0d1f08]",
  ivory:       "from-[#130b05] via-[#221508] to-[#2e1c0a]",
  milokira:    "from-[#f7f4eb] via-[#f0ece0] to-[#ede7d5]",
};

const DEFAULT_STYLES: StyleItem[] = [
  { id: "botanico",    name: "Botánico",    accent_hex: "#d2b234", is_custom: false },
  { id: "terracota",   name: "Terracota",   accent_hex: "#eb943e", is_custom: false },
  { id: "aesthetic",   name: "Aesthetic",   accent_hex: "#ecb2da", is_custom: false },
  { id: "dark_jungle", name: "Dark Jungle", accent_hex: "#48e673", is_custom: false },
  { id: "sage",        name: "Sage",        accent_hex: "#8abe69", is_custom: false },
  { id: "ivory",       name: "Ivory",       accent_hex: "#c8a869", is_custom: false },
  { id: "milokira",    name: "Milokira",    accent_hex: "#8da781", is_custom: false },
];

const STYLE_RING: Record<string, string> = {
  botanico:    "ring-yellow-500/40 bg-yellow-500/10 text-yellow-300",
  terracota:   "ring-orange-400/40 bg-orange-500/10 text-orange-300",
  aesthetic:   "ring-pink-300/40 bg-pink-500/10 text-pink-200",
  dark_jungle: "ring-emerald-400/40 bg-emerald-500/10 text-emerald-300",
  sage:        "ring-green-400/40 bg-green-500/10 text-green-300",
  ivory:       "ring-amber-300/40 bg-amber-500/10 text-amber-200",
  milokira:    "ring-stone-300/40 bg-stone-100/10 text-stone-300",
};

const STYLE_DOT: Record<string, string> = {
  botanico:    "bg-yellow-400",
  terracota:   "bg-orange-400",
  aesthetic:   "bg-fuchsia-300",
  dark_jungle: "bg-emerald-400",
  sage:        "bg-green-400",
  ivory:       "bg-amber-300",
  milokira:    "bg-[#8da781]",
};

function SlidesCreatorStudio() {
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("botanico");
  const [seriesPart, setSeriesPart] = useState<number | undefined>();
  const [slideCount, setSlideCount] = useState(5);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.getSlides>> | null>(null);
  const [slideIdx, setSlideIdx] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [publishState, setPublishState] = useState<Record<string, "idle" | "loading" | "done" | "error">>({});

  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const [generatingProfile, setGeneratingProfile] = useState(false);

  // Brand Kit modal
  const [brandKitProfileId, setBrandKitProfileId] = useState<string | null>(null);
  const [bkAccent, setBkAccent] = useState("#5a9e6a");
  const [bkHue, setBkHue] = useState("natural");
  const [bkDarkness, setBkDarkness] = useState("suave");
  const [bkFont, setBkFont] = useState("editorial");
  const [bkVoice, setBkVoice] = useState("");
  const [bkSaving, setBkSaving] = useState(false);
  const [liveLog, setLiveLog] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Slide text editor
  const [editingSlide, setEditingSlide] = useState(false);
  const [editHeadline, setEditHeadline] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [imgCacheBust, setImgCacheBust] = useState<Record<number, number>>({});

  // Dynamic styles — init with defaults so swatches show immediately
  const [styles, setStyles] = useState<StyleItem[]>(DEFAULT_STYLES);
  const [showStyleModal, setShowStyleModal] = useState(false);
  const [newStyleName, setNewStyleName] = useState("");
  const [newStyleAccent, setNewStyleAccent] = useState("#5a9e6a");
  const [newStyleHue, setNewStyleHue] = useState("natural");
  const [newStyleDarkness, setNewStyleDarkness] = useState("suave");
  const [creatingStyle, setCreatingStyle] = useState(false);

  // History
  type HistSet = { slug: string; title: string; style: string; created_at: string; image_count: number; has_video: boolean };
  const [history, setHistory] = useState<HistSet[]>([]);
  const [histLoading, setHistLoading] = useState(true);
  const [viewingSlug, setViewingSlug] = useState<string | null>(null);
  const [viewIdx, setViewIdx] = useState(0);

  function refreshHistory() {
    api.listSlides().then(r => { setHistory(r.sets); setHistLoading(false); }).catch(() => setHistLoading(false));
  }

  useEffect(() => {
    api.listProfiles().then(setProfiles).catch(() => {});
    // Merge default styles with any custom styles from API
    api.listStyles().then(d => {
      const custom = d.styles.filter(s => s.is_custom);
      setStyles([...DEFAULT_STYLES, ...custom]);
    }).catch(() => {}); // keep defaults on failure
    refreshHistory();
  }, []);

  async function createCustomStyle() {
    if (!newStyleName.trim()) return;
    setCreatingStyle(true);
    try {
      await api.createStyle(newStyleName.trim(), newStyleAccent, newStyleHue, newStyleDarkness);
      const d = await api.listStyles();
      setStyles(d.styles);
      const created = d.styles.find(s => s.name === newStyleName.trim() && s.is_custom);
      if (created) setStyle(created.id);
      setShowStyleModal(false);
      setNewStyleName("");
    } catch (e) {
      console.error(e);
    } finally {
      setCreatingStyle(false);
    }
  }

  async function deleteCustomStyle(id: string) {
    await api.deleteStyle(id).catch(() => {});
    setStyles(prev => prev.filter(s => s.id !== id));
    if (style === id) setStyle("botanico");
  }

  async function createProfile() {
    if (!newProfileName.trim()) return;
    setGeneratingProfile(true);
    try {
      const p = await api.createProfile(newProfileName.trim());
      setProfiles(prev => [...prev, p]);
      setSelectedProfile(p.id);
      setStyle(p.style);
      setNewProfileName("");
      setCreatingProfile(false);
    } finally {
      setGeneratingProfile(false);
    }
  }

  function selectProfile(id: string | null) {
    setSelectedProfile(id);
    if (id) {
      const p = profiles.find(pr => pr.id === id);
      if (p && !p.brand_accent_hex) setStyle(p.style);
    }
  }

  function openBrandKit(p: ProfileItem) {
    setBkAccent(p.brand_accent_hex ?? "#5a9e6a");
    setBkHue(p.brand_base_hue ?? "natural");
    setBkDarkness(p.brand_darkness ?? "suave");
    setBkFont(p.brand_font ?? "editorial");
    setBkVoice(p.brand_voice ?? "");
    setBrandKitProfileId(p.id);
  }

  async function saveBrandKit() {
    if (!brandKitProfileId) return;
    setBkSaving(true);
    try {
      const updated = await api.saveBrandKit(brandKitProfileId, {
        accent_hex: bkAccent, base_hue: bkHue, darkness: bkDarkness,
        font: bkFont, voice: bkVoice || null,
      });
      setProfiles(prev => prev.map(p => p.id === brandKitProfileId ? updated : p));
      setBrandKitProfileId(null);
    } finally {
      setBkSaving(false);
    }
  }

  async function clearBrandKit(profileId: string) {
    const updated = await api.saveBrandKit(profileId, {
      accent_hex: null, base_hue: null, darkness: null, font: null, voice: null,
    });
    setProfiles(prev => prev.map(p => p.id === profileId ? updated : p));
  }

  useEffect(() => {
    if (!jobId || status !== "running") return;
    const iv = setInterval(async () => {
      const job = await api.getJob(jobId).catch(() => null);
      if (!job) return;
      // Show latest log line so user sees real progress
      if (job.logs?.length) setLiveLog(job.logs[job.logs.length - 1]);
      if (job.status === "done") {
        setStatus("done");
        setLiveLog("");
        const clips = job.clips as { slug?: string }[];
        if (clips?.[0]?.slug) {
          const meta = await api.getSlides(clips[0].slug).catch(() => null);
          if (meta) { setResult(meta); setSlideIdx(0); refreshHistory(); }
        }
        clearInterval(iv);
      } else if (job.status === "error") {
        const lastLog = job.logs?.length ? job.logs[job.logs.length - 1] : "";
        setStatus("error"); setLiveLog(lastLog); setErrorMsg(job.error ?? ""); clearInterval(iv);
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [jobId, status]);

  async function generate() {
    if (!topic.trim()) return;
    setStatus("running"); setResult(null); setViewingSlug(null); setErrorMsg("");
    const { job_id } = await api.createSlides(topic.trim(), style, seriesPart, selectedProfile ?? "", slideCount);
    setJobId(job_id);
  }

  function copyHashtags(platform: string) {
    if (!result) return;
    const tags = (result.hashtags[platform] || []).join(" ");
    navigator.clipboard.writeText(tags);
    setCopied(platform);
    setTimeout(() => setCopied(null), 2000);
  }

  async function publishSlides(platform: "instagram" | "tiktok") {
    if (!result) return;
    setPublishState(s => ({ ...s, [platform]: "loading" }));
    try {
      await fetch(`/api/slides/${result.slug}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform }),
      });
      setPublishState(s => ({ ...s, [platform]: "done" }));
    } catch {
      setPublishState(s => ({ ...s, [platform]: "error" }));
    }
  }

  const GEN_STEPS = ["Contenido", "Fotos", "Slides"];

  // History viewer open
  const histViewed = history.find(s => s.slug === viewingSlug);

  return (
    <div className="relative">
      {/* Studio 2-column grid */}
      <div className="grid lg:grid-cols-[390px_1fr] min-h-[680px] rounded-2xl overflow-hidden border border-zinc-800/60 bg-gradient-to-br from-zinc-900/95 to-zinc-950">

      {/* ═══════════════ LEFT PANEL — Controls ═══════════════ */}
      <div className="border-r border-zinc-800/50 flex flex-col">
        {/* Header */}
        <div className="px-5 pt-5 pb-3 border-b border-zinc-800/40">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <span className="text-zinc-200 font-semibold text-sm">Generar carrusel</span>
          </div>
        </div>

        <div className="flex-1 p-5 space-y-4 overflow-y-auto">
        {/* ambient top glow */}
        <div className="pointer-events-none absolute -top-32 left-0 w-80 h-40 bg-emerald-500/4 blur-3xl" />

          {/* Profiles ─────────────────────────────────────────────────────── */}
          <div className="space-y-2.5">
            <div className="flex gap-1.5 flex-wrap items-center">
              <span className="text-zinc-600 text-[11px] uppercase tracking-widest font-medium mr-1">Modo</span>

              <button onClick={() => selectProfile(null)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                  !selectedProfile
                    ? "bg-zinc-700 text-zinc-200"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/80"
                }`}>
                General
              </button>

              {profiles.map(p => {
                const active    = selectedProfile === p.id;
                const hasBrand  = !!p.brand_accent_hex;
                const ring      = STYLE_RING[p.style] ?? "ring-zinc-500/40 bg-zinc-700/20 text-zinc-300";
                const dot       = STYLE_DOT[p.style]  ?? "bg-zinc-400";
                const brandRing = hasBrand ? "ring-1" : "";
                return (
                  <div key={p.id} className="group relative flex items-center gap-0.5">
                    <button onClick={() => selectProfile(p.id)}
                      className={`pl-2.5 pr-2 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
                        active
                          ? hasBrand ? `${brandRing} ring-zinc-500/40 bg-zinc-700/30 text-zinc-200` : `ring-1 ${ring}`
                          : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/80"
                      }`}>
                      {hasBrand
                        ? <span className="w-2 h-2 rounded-full shrink-0 ring-1 ring-white/20"
                            style={{ backgroundColor: p.brand_accent_hex! }} />
                        : <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active ? dot : "bg-zinc-600"}`} />
                      }
                      {p.name}
                      {hasBrand && <Palette className="w-2.5 h-2.5 text-zinc-500 shrink-0" />}
                    </button>
                    {/* Brand kit button */}
                    <button
                      onClick={e => { e.stopPropagation(); openBrandKit(p); }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-full text-zinc-600 hover:text-emerald-400 hover:bg-zinc-800">
                      <Palette className="w-3 h-3" />
                    </button>
                    {/* Delete button */}
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        await api.deleteProfile(p.id).catch(() => {});
                        setProfiles(prev => prev.filter(x => x.id !== p.id));
                        if (selectedProfile === p.id) setSelectedProfile(null);
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-full text-zinc-600 hover:text-red-400 hover:bg-zinc-800">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                );
              })}

              {creatingProfile ? (
                <div className="flex items-center gap-1.5 ml-1">
                  <input
                    value={newProfileName}
                    onChange={e => setNewProfileName(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && createProfile()}
                    placeholder="ej. Cocina saludable, Fitness..."
                    autoFocus
                    className="bg-zinc-800/80 border border-zinc-700/60 rounded-full px-3.5 py-1 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/60 w-48 transition"
                  />
                  <button onClick={createProfile} disabled={!newProfileName.trim() || generatingProfile}
                    className="px-3 py-1 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium disabled:opacity-40 flex items-center gap-1.5 transition-all shrink-0">
                    {generatingProfile ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    {generatingProfile ? "Creando..." : "Crear"}
                  </button>
                  <button onClick={() => { setCreatingProfile(false); setNewProfileName(""); }}
                    className="p-1 rounded-full text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800 transition">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <button onClick={() => setCreatingProfile(true)}
                  className="ml-1 flex items-center gap-1.5 px-3 py-1 rounded-full text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/80 text-xs font-medium transition-all border border-zinc-800 hover:border-zinc-700">
                  <Sparkles className="w-3 h-3" /> Nueva categoría
                </button>
              )}
            </div>

            {/* Suggested topics */}
            <AnimatePresence>
              {selectedProfile && (() => {
                const p = profiles.find(pr => pr.id === selectedProfile);
                if (!p?.content_angles?.length) return null;
                return (
                  <motion.div key={p.id}
                    initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.15 }}
                    className="flex gap-1.5 flex-wrap items-center pl-1">
                    <span className="text-zinc-600 text-[11px] shrink-0">Temas:</span>
                    {p.content_angles.map((angle, i) => (
                      <button key={i} onClick={() => setTopic(angle)}
                        className="px-2.5 py-0.5 rounded-full bg-zinc-800/80 hover:bg-emerald-950/70 text-zinc-400 hover:text-emerald-300 text-xs border border-zinc-700/50 hover:border-emerald-800/60 transition-all">
                        {angle}
                      </button>
                    ))}
                  </motion.div>
                );
              })()}
            </AnimatePresence>
          </div>

          {/* Divider */}
          <div className="h-px bg-gradient-to-r from-transparent via-zinc-700/40 to-transparent" />

          {/* Input + Generate ──────────────────────────────────────────────── */}
          <div className="relative">
            <textarea
              value={topic}
              onChange={e => setTopic(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), generate())}
              placeholder="¿Sobre qué quieres crear contenido? ej. suculentas de interior, finanzas para millennials…"
              rows={2}
              className="w-full resize-none bg-zinc-800/60 border border-zinc-700/60 rounded-xl px-4 py-3.5 pr-36 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/15 transition leading-relaxed"
            />
            <button onClick={generate} disabled={status === "running" || !topic.trim()}
              className="absolute right-2.5 bottom-2.5 px-4 py-2 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-40 text-white text-sm font-semibold flex items-center gap-2 transition-all shadow-lg shadow-emerald-900/40 hover:shadow-emerald-900/60 active:scale-95">
              {status === "running" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {status === "running" ? "Generando" : "Generar"}
            </button>
          </div>

          {/* Style swatches + serie ──────────────────────────────────────── */}
          <div className="space-y-2">
            {/* Brand kit active badge — replaces style picker when profile has brand kit */}
            {selectedProfile && profiles.find(p => p.id === selectedProfile)?.brand_accent_hex && (() => {
              const p = profiles.find(pr => pr.id === selectedProfile)!;
              return (
                <div className="flex items-center gap-2 p-2.5 rounded-xl bg-zinc-800/60 border border-zinc-700/40">
                  <span className="w-3 h-3 rounded-full ring-1 ring-white/20 shrink-0"
                    style={{ backgroundColor: p.brand_accent_hex! }} />
                  <span className="text-zinc-300 text-xs font-medium flex-1">Brand Kit activo — {p.name}</span>
                  <button onClick={() => openBrandKit(p)}
                    className="text-zinc-500 hover:text-emerald-400 transition-colors text-xs flex items-center gap-1">
                    <Palette className="w-3 h-3" /> Editar
                  </button>
                </div>
              );
            })()}

            <div className={selectedProfile && profiles.find(p => p.id === selectedProfile)?.brand_accent_hex ? "opacity-30 pointer-events-none space-y-2" : "space-y-2"}>
              <div className="flex items-center gap-2">
                <span className="text-zinc-600 text-[11px] uppercase tracking-widest font-medium">Estilo</span>
                <div className="ml-auto flex items-center gap-1.5">
                  <span className="text-zinc-700 text-[10px] mr-0.5">Slides</span>
                  <div className="flex items-center gap-0.5 bg-zinc-800/80 border border-zinc-700/50 rounded-lg p-0.5">
                    {[1,2,3,4,5,6,7,8,9,10].map(n => (
                      <button key={n} onClick={() => setSlideCount(n)}
                        className={`w-6 h-6 rounded-md text-[11px] font-medium transition-all ${
                          slideCount === n
                            ? "bg-emerald-600 text-white shadow-sm"
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}>
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex gap-2 flex-wrap items-center">
                {styles.map(s => {
                  const isActive = style === s.id;
                  const swatch = BUILTIN_SWATCHES[s.id];
                  return (
                    <div key={s.id} className="relative group/swatch">
                      <button onClick={() => setStyle(s.id)}
                        className={`relative h-10 w-[4.5rem] rounded-xl overflow-hidden border transition-all duration-200 ${
                          isActive
                            ? "border-white/25 ring-1 ring-white/20 scale-105 shadow-lg shadow-black/40"
                            : "border-zinc-700/50 hover:border-zinc-500 opacity-55 hover:opacity-95 hover:scale-[1.03]"
                        }`}>
                        {swatch ? (
                          <div className={`absolute inset-0 bg-gradient-to-br ${swatch}`} />
                        ) : (
                          <div className="absolute inset-0" style={{
                            background: `linear-gradient(135deg, ${s.accent_hex}18 0%, ${s.accent_hex}55 100%)`
                          }} />
                        )}
                        {isActive && (
                          <div className="absolute inset-0 bg-gradient-to-tr from-white/[0.04] to-transparent" />
                        )}
                        <div className="absolute inset-0 flex items-end justify-start px-2 pb-1.5">
                          <span className={`text-[9px] font-semibold leading-none line-clamp-1 ${s.id === "milokira" ? "text-stone-600/90" : "text-white/90 drop-shadow-md"}`}>
                            {s.name}
                          </span>
                        </div>
                        <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full opacity-90"
                              style={{ backgroundColor: s.accent_hex }} />
                      </button>
                      {s.is_custom && (
                        <button
                          onClick={() => deleteCustomStyle(s.id)}
                          className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-zinc-800 border border-zinc-600 text-zinc-400 hover:text-white hover:bg-red-900/60 flex items-center justify-center opacity-0 group-hover/swatch:opacity-100 transition-opacity z-10">
                          <X className="w-2.5 h-2.5" />
                        </button>
                      )}
                    </div>
                  );
                })}
                <button onClick={() => setShowStyleModal(true)}
                  className="h-10 w-10 rounded-xl border border-dashed border-zinc-600/70 hover:border-zinc-400 text-zinc-600 hover:text-zinc-300 flex items-center justify-center transition-all hover:bg-zinc-800/40 shrink-0"
                  title="Crear estilo personalizado">
                  <span className="text-xl leading-none">+</span>
                </button>
              </div>
            </div>
          </div>

          {/* Custom style creation modal */}
          <AnimatePresence>
            {showStyleModal && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
                onClick={() => setShowStyleModal(false)}>
                <motion.div initial={{ scale: 0.94, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.94, y: 10 }}
                  transition={{ type: "spring", stiffness: 340, damping: 28 }}
                  className="bg-zinc-900 border border-zinc-700/60 rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl"
                  onClick={e => e.stopPropagation()}>
                  <div className="flex items-center justify-between">
                    <h3 className="text-white font-semibold text-[15px]">Nuevo estilo personalizado</h3>
                    <button onClick={() => setShowStyleModal(false)} className="text-zinc-500 hover:text-zinc-300 p-1">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="space-y-3">
                    <input value={newStyleName} onChange={e => setNewStyleName(e.target.value)}
                      placeholder="Nombre del estilo…"
                      className="w-full bg-zinc-800/80 border border-zinc-700/60 rounded-xl px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 transition" />
                    <div className="flex items-center gap-3">
                      <label className="text-zinc-500 text-xs shrink-0">Color acento</label>
                      <div className="relative">
                        <input type="color" value={newStyleAccent}
                          onChange={e => setNewStyleAccent(e.target.value)}
                          className="w-10 h-10 rounded-xl border-2 border-zinc-700 bg-zinc-800 cursor-pointer p-0.5" />
                      </div>
                      <div className="h-10 flex-1 rounded-xl border border-zinc-700/60 overflow-hidden">
                        <div className="w-full h-full" style={{
                          background: `linear-gradient(135deg, ${newStyleAccent}18, ${newStyleAccent}88)`
                        }} />
                      </div>
                      <span className="text-zinc-500 text-[11px] font-mono">{newStyleAccent}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-zinc-500 text-[11px] mb-1.5 block uppercase tracking-wider">Paleta</label>
                        <select value={newStyleHue} onChange={e => setNewStyleHue(e.target.value)}
                          className="w-full bg-zinc-800 border border-zinc-700/60 rounded-xl px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:border-zinc-500 transition cursor-pointer">
                          <option value="natural">Natural</option>
                          <option value="calido">Cálido</option>
                          <option value="frio">Frío</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-zinc-500 text-[11px] mb-1.5 block uppercase tracking-wider">Oscuridad</label>
                        <select value={newStyleDarkness} onChange={e => setNewStyleDarkness(e.target.value)}
                          className="w-full bg-zinc-800 border border-zinc-700/60 rounded-xl px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:border-zinc-500 transition cursor-pointer">
                          <option value="claro">Claro</option>
                          <option value="suave">Suave</option>
                          <option value="oscuro">Oscuro</option>
                        </select>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button onClick={() => setShowStyleModal(false)}
                      className="flex-1 py-2.5 rounded-xl border border-zinc-700 text-zinc-400 text-sm hover:bg-zinc-800 transition-colors">
                      Cancelar
                    </button>
                    <button onClick={createCustomStyle}
                      disabled={!newStyleName.trim() || creatingStyle}
                      className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2">
                      {creatingStyle && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      Crear estilo
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Brand Kit modal */}
          <AnimatePresence>
            {brandKitProfileId && (() => {
              const profileName = profiles.find(p => p.id === brandKitProfileId)?.name ?? "";
              return (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
                  onClick={() => setBrandKitProfileId(null)}>
                  <motion.div initial={{ scale: 0.94, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.94, y: 10 }}
                    transition={{ type: "spring", stiffness: 340, damping: 28 }}
                    className="bg-zinc-900 border border-zinc-700/60 rounded-2xl p-6 w-full max-w-md space-y-5 shadow-2xl"
                    onClick={e => e.stopPropagation()}>
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-white font-semibold text-[15px] flex items-center gap-2">
                          <Palette className="w-4 h-4 text-emerald-400" /> Brand Kit
                        </h3>
                        <p className="text-zinc-500 text-xs mt-0.5">{profileName}</p>
                      </div>
                      <button onClick={() => setBrandKitProfileId(null)} className="text-zinc-500 hover:text-zinc-300 p-1">
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Color acento */}
                    <div className="space-y-2">
                      <label className="text-zinc-400 text-[11px] uppercase tracking-wider block">Color de marca</label>
                      <div className="flex items-center gap-3">
                        <input type="color" value={bkAccent} onChange={e => setBkAccent(e.target.value)}
                          className="w-12 h-10 rounded-xl border-2 border-zinc-700 bg-zinc-800 cursor-pointer p-0.5 shrink-0" />
                        <div className="h-10 flex-1 rounded-xl border border-zinc-700/60 overflow-hidden">
                          <div className="w-full h-full" style={{ background: `linear-gradient(135deg, ${bkAccent}20, ${bkAccent}80)` }} />
                        </div>
                        <span className="text-zinc-500 text-[11px] font-mono">{bkAccent}</span>
                      </div>
                    </div>

                    {/* Paleta + oscuridad */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-zinc-400 text-[11px] uppercase tracking-wider mb-1.5 block">Paleta base</label>
                        <select value={bkHue} onChange={e => setBkHue(e.target.value)}
                          className="w-full bg-zinc-800 border border-zinc-700/60 rounded-xl px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:border-zinc-500 transition cursor-pointer">
                          <option value="natural">Natural</option>
                          <option value="calido">Cálido</option>
                          <option value="frio">Frío</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-zinc-400 text-[11px] uppercase tracking-wider mb-1.5 block">Oscuridad</label>
                        <select value={bkDarkness} onChange={e => setBkDarkness(e.target.value)}
                          className="w-full bg-zinc-800 border border-zinc-700/60 rounded-xl px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:border-zinc-500 transition cursor-pointer">
                          <option value="claro">Claro</option>
                          <option value="suave">Suave</option>
                          <option value="oscuro">Oscuro</option>
                        </select>
                      </div>
                    </div>

                    {/* Tipografía */}
                    <div>
                      <label className="text-zinc-400 text-[11px] uppercase tracking-wider mb-2 block">Estilo tipográfico</label>
                      <div className="grid grid-cols-3 gap-2">
                        {[
                          { id: "editorial", label: "Editorial", desc: "Playfair Bold" },
                          { id: "moderno",   label: "Moderno",   desc: "Sans Bold" },
                          { id: "elegante",  label: "Elegante",  desc: "Playfair Light" },
                        ].map(f => (
                          <button key={f.id} onClick={() => setBkFont(f.id)}
                            className={`p-2.5 rounded-xl border text-center transition-all ${
                              bkFont === f.id
                                ? "border-emerald-500/60 bg-emerald-950/40 text-emerald-300"
                                : "border-zinc-700/60 hover:border-zinc-600 text-zinc-400 hover:text-zinc-300"
                            }`}>
                            <span className="text-xs font-medium block">{f.label}</span>
                            <span className="text-[10px] text-zinc-500 block">{f.desc}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Voz de marca */}
                    <div>
                      <label className="text-zinc-400 text-[11px] uppercase tracking-wider mb-1.5 block">Voz de marca</label>
                      <textarea
                        value={bkVoice}
                        onChange={e => setBkVoice(e.target.value)}
                        placeholder="Ej: Tono cercano y educativo. Nunca usar anglicismos. Siempre mencionar la especie científica. Priorizar datos concretos sobre consejos genéricos…"
                        rows={3}
                        className="w-full bg-zinc-800/80 border border-zinc-700/60 rounded-xl px-3 py-2.5 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 transition resize-none"
                      />
                      <p className="text-zinc-600 text-[10px] mt-1">Instrucciones extra para Gemini al generar contenido de este perfil.</p>
                    </div>

                    <div className="flex gap-2 pt-1">
                      <button onClick={() => setBrandKitProfileId(null)}
                        className="flex-1 py-2.5 rounded-xl border border-zinc-700 text-zinc-400 text-sm hover:bg-zinc-800 transition-colors">
                        Cancelar
                      </button>
                      <button onClick={saveBrandKit} disabled={bkSaving}
                        className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2">
                        {bkSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                        Guardar brand kit
                      </button>
                    </div>
                  </motion.div>
                </motion.div>
              );
            })()}
          </AnimatePresence>

          {/* Progress steps */}
          <AnimatePresence>
            {status === "running" && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="pt-1">
                <div className="h-0.5 w-full bg-zinc-800/80 rounded-full overflow-hidden">
                  <motion.div className="h-full bg-emerald-500/60 rounded-full"
                    animate={{ width: ["8%", "55%", "80%", "92%"] }}
                    transition={{ duration: 28, ease: "easeOut" }} />
                </div>
              </motion.div>
            )}
            {status === "error" && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="rounded-xl border border-red-500/20 bg-red-500/5 p-3 space-y-1.5">
                <p className="text-red-400 text-sm flex items-center gap-2 font-medium">
                  <XCircle className="w-4 h-4 shrink-0" /> Error generando slides
                </p>
                {liveLog && (
                  <p className="text-zinc-500 text-xs font-mono">último paso: {liveLog}</p>
                )}
                {errorMsg && (
                  <p className="text-red-400/60 text-xs font-mono break-all leading-relaxed">{errorMsg}</p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>{/* end flex-1 scroll */}
      </div>{/* end LEFT PANEL */}

      {/* ═══════════════ RIGHT PANEL — Dynamic ═══════════════ */}
      <div className="flex flex-col overflow-hidden">
        <AnimatePresence mode="wait">

          {/* ── GENERATING: skeleton slides ── */}
          {status === "running" && (
            <motion.div key="generating"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex-1 p-5 flex flex-col gap-4">
              {/* Generation header — active step derived from liveLog */}
              {(() => {
                const activeStep = liveLog.toLowerCase().includes("imagen") || liveLog.toLowerCase().includes("foto") || liveLog.toLowerCase().includes("descarg")
                  ? 1
                  : liveLog.toLowerCase().includes("compon") || liveLog.toLowerCase().includes("slide") || liveLog.toLowerCase().includes("listo")
                  ? 2 : 0;
                return (
                  <div className="flex items-center justify-between pb-2">
                    <div className="flex items-center gap-2.5">
                      <Loader2 className="w-3.5 h-3.5 text-emerald-400 animate-spin shrink-0" />
                      <span className="text-zinc-300 text-sm font-medium truncate max-w-[180px]">{topic}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {["Contenido", "Fotos", "Slides"].map((step, i) => (
                        <div key={i} className="flex items-center gap-1">
                          <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all duration-500 ${
                            i === activeStep
                              ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30"
                              : i < activeStep
                              ? "text-zinc-500 line-through"
                              : "text-zinc-700"
                          }`}>
                            {i < activeStep && <Check className="w-2.5 h-2.5 mr-0.5" />}
                            {i === activeStep && <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.2, repeat: Infinity }} className="w-1 h-1 rounded-full bg-emerald-400 mr-1 inline-block" />}
                            {step}
                          </div>
                          {i < 2 && <span className="text-zinc-800 text-[9px]">›</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
              <div className={`grid gap-2 ${slideCount <= 5 ? "grid-cols-3 sm:grid-cols-5" : slideCount <= 7 ? "grid-cols-4 sm:grid-cols-5" : "grid-cols-4 sm:grid-cols-5"}`}>
                {Array.from({ length: slideCount }).map((_, i) => (
                  <motion.div key={i}
                    initial={{ opacity: 0, scale: 0.9, y: 8 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ delay: i * 0.055, duration: 0.3 }}
                    className="aspect-[4/5] rounded-xl bg-zinc-800/70 overflow-hidden relative">
                    <div className="absolute inset-0 bg-gradient-to-b from-zinc-700/20 to-zinc-800/60 animate-pulse" />
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.04] to-transparent"
                      animate={{ x: ["-100%", "200%"] }}
                      transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }}
                    />
                    <span className="absolute bottom-2 left-2 text-zinc-600 text-[10px] font-mono">{String(i + 1).padStart(2, "0")}</span>
                  </motion.div>
                ))}
              </div>
              {liveLog && (
                <motion.p key={liveLog} initial={{ opacity: 0, y: 2 }} animate={{ opacity: 1, y: 0 }}
                  className="text-zinc-600 text-[10px] font-mono truncate">
                  {liveLog}
                </motion.p>
              )}
            </motion.div>
          )}

          {/* ── DONE: carousel viewer ── */}
          {status === "done" && result && (
            <motion.div key="viewer"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex-1 flex flex-col overflow-hidden">
              {/* Viewer header */}
              <div className="flex items-start justify-between px-5 pt-4 pb-3 border-b border-zinc-800/40">
                <div>
                  <h3 className="text-zinc-100 font-semibold text-sm leading-snug line-clamp-1">{result.title}</h3>
                  <p className="text-zinc-500 text-[11px] mt-0.5">{result.images.length} slides · {result.style}</p>
                </div>
                <button onClick={() => { setStatus("idle"); setResult(null); }}
                  className="text-zinc-600 hover:text-zinc-300 p-1.5 hover:bg-zinc-800 rounded-lg transition-colors">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              {/* Carousel */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
                <div className="flex items-center justify-center gap-4">
                  <button onClick={() => { setSlideIdx(i => Math.max(0, i - 1)); setEditingSlide(false); }} disabled={slideIdx === 0}
                    className="p-2 rounded-full bg-zinc-800/80 hover:bg-zinc-700 disabled:opacity-20 border border-zinc-700/40 transition-all">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <div className="relative cursor-zoom-in group" onClick={() => setLightboxOpen(true)}>
                    <div className="w-64 aspect-[4/5] rounded-2xl overflow-hidden shadow-2xl ring-1 ring-white/5 group-hover:ring-emerald-500/20 transition-all">
                      <img
                        src={api.slideImageUrl(result.slug, result.images[slideIdx]) + (imgCacheBust[slideIdx] ? `?t=${imgCacheBust[slideIdx]}` : "")}
                        alt={`Slide ${slideIdx + 1}`}
                        className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300" />
                    </div>
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <div className="bg-black/50 backdrop-blur-sm rounded-full px-2.5 py-1 text-white text-xs flex items-center gap-1.5">
                        <ImageIcon className="w-3 h-3" /> Ampliar
                      </div>
                    </div>
                  </div>
                  <button onClick={() => { setSlideIdx(i => Math.min(result.images.length - 1, i + 1)); setEditingSlide(false); }} disabled={slideIdx === result.images.length - 1}
                    className="p-2 rounded-full bg-zinc-800/80 hover:bg-zinc-700 disabled:opacity-20 border border-zinc-700/40 transition-all">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
                {/* Dots */}
                <div className="flex justify-center gap-1">
                  {result.images.map((_, i) => (
                    <button key={i} onClick={() => { setSlideIdx(i); setEditingSlide(false); }}
                      className={`rounded-full transition-all duration-200 ${i === slideIdx ? "w-5 h-1.5 bg-emerald-400" : "w-1.5 h-1.5 bg-zinc-700 hover:bg-zinc-500"}`} />
                  ))}
                </div>
                {/* Actions */}
                <div className="flex gap-1.5 flex-wrap pt-0.5">
                  <a href={api.slideImageUrl(result.slug, result.images[slideIdx])} download
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs transition-all border border-zinc-700/40">
                    <Download className="w-3 h-3" /> Slide {slideIdx + 1}
                  </a>
                  <a href={api.slideZipUrl(result.slug)} download
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs transition-all border border-zinc-700/40">
                    <Download className="w-3 h-3" /> ZIP
                  </a>
                  {result.video && (
                    <a href={api.slideVideoUrl(result.slug)} download
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-900/30 border border-emerald-500/20 text-emerald-400 hover:text-emerald-300 text-xs transition-all">
                      <Download className="w-3 h-3" /> Video
                    </a>
                  )}
                  {(["instagram", "tiktok", "pinterest"] as const).map(p => (
                    <button key={p} onClick={() => copyHashtags(p)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs transition-all border border-zinc-700/40">
                      <Copy className="w-3 h-3" />
                      {copied === p ? "✓" : `#${p}`}
                    </button>
                  ))}
                </div>
                {/* ── Text editor ── */}
                <div className="border-t border-zinc-800/40 pt-3">
                  {!editingSlide ? (
                    <button
                      onClick={() => {
                        const slide = result.slides?.[slideIdx];
                        setEditHeadline(slide?.headline ?? "");
                        setEditBody(slide?.body ?? "");
                        setEditingSlide(true);
                      }}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-zinc-800/60 hover:bg-zinc-700/60 text-zinc-400 hover:text-zinc-200 text-xs transition-all border border-zinc-700/30">
                      <Pencil className="w-3 h-3" /> Editar texto del slide {slideIdx + 1}
                    </button>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-zinc-600 text-[10px] uppercase tracking-widest font-medium">Editando slide {slideIdx + 1}</p>
                      <div>
                        <label className="text-zinc-500 text-[10px] mb-1 block">Titular</label>
                        <textarea value={editHeadline} onChange={e => setEditHeadline(e.target.value)}
                          rows={2}
                          className="w-full bg-zinc-800 border border-zinc-700/50 rounded-lg px-3 py-2 text-zinc-200 text-xs resize-none focus:outline-none focus:border-emerald-500/50 transition-colors" />
                      </div>
                      <div>
                        <label className="text-zinc-500 text-[10px] mb-1 block">Cuerpo</label>
                        <textarea value={editBody} onChange={e => setEditBody(e.target.value)}
                          rows={3}
                          className="w-full bg-zinc-800 border border-zinc-700/50 rounded-lg px-3 py-2 text-zinc-200 text-xs resize-none focus:outline-none focus:border-emerald-500/50 transition-colors" />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={async () => {
                            setEditSaving(true);
                            try {
                              await api.updateSlide(result.slug, slideIdx, {
                                headline: editHeadline,
                                body: editBody,
                              });
                              setImgCacheBust(p => ({ ...p, [slideIdx]: Date.now() }));
                              setEditingSlide(false);
                            } catch { /* noop */ }
                            setEditSaving(false);
                          }}
                          disabled={editSaving}
                          className="flex-1 flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium transition-all">
                          {editSaving ? "Aplicando..." : "Aplicar"}
                        </button>
                        <button onClick={() => setEditingSlide(false)}
                          className="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs transition-all border border-zinc-700/40">
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Hook variants */}
                {result.hook_variants?.length > 0 && (
                  <div className="space-y-1 pt-2 border-t border-zinc-800/40">
                    <p className="text-zinc-600 text-[10px] uppercase tracking-widest font-medium mb-1.5">Variantes del hook</p>
                    {result.hook_variants.map((h, i) => (
                      <div key={i} className="flex items-start gap-2 bg-zinc-800/40 rounded-lg px-3 py-2 group/hook border border-zinc-700/20">
                        <span className="text-zinc-600 font-mono text-[10px] shrink-0 mt-0.5">{String.fromCharCode(65+i)}</span>
                        <span className="text-zinc-300 text-xs leading-snug">{h}</span>
                        <button onClick={() => navigator.clipboard.writeText(h)}
                          className="ml-auto text-zinc-700 hover:text-zinc-300 shrink-0 opacity-0 group-hover/hook:opacity-100 transition-opacity">
                          <Copy size={10} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* ── IDLE / HISTORY: thumbnail grid ── */}
          {(status === "idle" || status === "error") && (
            <motion.div key="history"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex-1 overflow-y-auto p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <LayoutGrid className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-zinc-500 text-xs uppercase tracking-widest font-medium">Carruseles</span>
                  {history.length > 0 && (
                    <span className="bg-zinc-800 text-zinc-500 text-[10px] px-1.5 py-0.5 rounded-full">{history.length}</span>
                  )}
                </div>
              </div>

              {histLoading ? (
                <div className="grid grid-cols-3 gap-2.5">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="aspect-[4/5] rounded-xl bg-zinc-800/60 animate-pulse" />
                  ))}
                </div>
              ) : history.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-64 gap-3 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-zinc-800/60 border border-zinc-700/40 flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-zinc-600" />
                  </div>
                  <p className="text-zinc-500 text-sm font-medium">Sin carruseles aún</p>
                  <p className="text-zinc-700 text-xs">Escribe un tema y genera tu primer carrusel</p>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-2.5">
                  {history.map(s => (
                    <button key={s.slug} onClick={() => {
                      api.getSlides(s.slug).then(meta => {
                        setResult(meta); setSlideIdx(0); setStatus("done"); setViewingSlug(s.slug);
                      }).catch(() => {});
                    }}
                      className="group relative aspect-[4/5] rounded-xl overflow-hidden border border-zinc-800/60 hover:border-zinc-600/80 transition-all hover:shadow-lg hover:shadow-black/40">
                      <img
                        src={api.slideImageUrl(s.slug, "00.png")}
                        alt={s.title}
                        className="w-full h-full object-cover group-hover:scale-[1.04] transition-transform duration-400"
                        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                      <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/90 via-black/40 to-transparent">
                        <p className="text-white text-[10px] font-semibold leading-tight line-clamp-2">{s.title}</p>
                        <p className="text-white/40 text-[9px] mt-0.5">{s.image_count} slides</p>
                      </div>
                      {s.has_video && (
                        <div className="absolute top-1.5 right-1.5 bg-emerald-500/80 rounded-full p-0.5">
                          <Play className="w-2.5 h-2.5 text-white fill-white" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </motion.div>
          )}

        </AnimatePresence>
      </div>{/* end RIGHT PANEL */}

      </div>{/* end 2-col grid */}

      {/* Fullscreen lightbox */}
      <AnimatePresence>
        {lightboxOpen && result && (
          <SlideModal
            images={result.images} slug={result.slug}
            current={slideIdx} total={result.images.length}
            onClose={() => setLightboxOpen(false)}
            onGoto={(i) => setSlideIdx(i)}
          />
        )}
      </AnimatePresence>
    </div>
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
    setLoading(true); setError(""); setInsights([]);
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
      <div className="flex items-center gap-2 flex-wrap">
        {[7, 28, 90].map((d) => (
          <button key={d} onClick={() => { setDays(d); load(d); }}
            className={`text-sm px-4 py-2 rounded-xl border transition-all ${days === d ? "bg-zinc-800 border-zinc-600 text-zinc-100" : "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400"}`}>
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
              { val: `${best.retention_pct}%`,          label: "Retención media", color: "text-red-400" },
              { val: fmt(best.views),                    label: "Vistas totales",  color: "text-zinc-100" },
              { val: fmtDur(best.avg_view_duration_s),   label: "Dur. promedio",   color: "text-violet-400" },
              { val: `+${best.subs_gained}`,             label: "Subs ganados",    color: "text-green-400" },
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
                      className="hover:text-red-400 transition-colors text-zinc-300 line-clamp-1 block max-w-xs text-xs font-medium">{r.title}</a>
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
