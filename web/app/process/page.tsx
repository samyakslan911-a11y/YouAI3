"use client";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, type Job } from "@/lib/api";
import Link from "next/link";
import { Suspense } from "react";

function ProcessContent() {
  const params = useSearchParams();
  const [url, setUrl] = useState(params.get("url") ?? "");
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const logsEndRef = useRef<HTMLDivElement>(null);

  async function start() {
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    setJob(null);
    try {
      const res = await api.createJob(url);
      setJobId(res.job_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al iniciar");
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const j = await api.getJob(jobId);
        setJob(j);
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
        if (j.status === "done" || j.status === "error") {
          clearInterval(interval);
          setLoading(false);
        }
      } catch {
        clearInterval(interval);
        setLoading(false);
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [jobId]);

  const statusColor = { queued: "text-zinc-400", running: "text-yellow-400", done: "text-green-400", error: "text-red-400" };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-1">Procesar video</h1>
        <p className="text-zinc-400 text-sm">Pega una URL de YouTube para extraer clips virales automáticamente</p>
      </div>

      {/* URL input */}
      <div className="flex gap-3">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && start()}
          placeholder="https://youtu.be/..."
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-red-500"
        />
        <button
          onClick={start}
          disabled={loading}
          className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg px-6 py-2.5 text-sm font-medium transition-colors"
        >
          {loading ? "Procesando..." : "Generar clips"}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Job status */}
      {job && (
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-400">Estado:</span>
            <span className={`text-sm font-medium ${statusColor[job.status]}`}>
              {job.status === "queued" && "En cola"}
              {job.status === "running" && "Procesando..."}
              {job.status === "done" && `Listo — ${job.clips.length} clips`}
              {job.status === "error" && `Error: ${job.error}`}
            </span>
            {job.status === "running" && (
              <span className="inline-block w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
            )}
          </div>

          {/* Logs */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 max-h-48 overflow-y-auto font-mono text-xs text-zinc-400 space-y-1">
            {job.logs.map((l, i) => (
              <p key={i} className={l.includes("Error") || l.includes("error") ? "text-red-400" : l.includes("listo") || l.includes("completado") ? "text-green-400" : ""}>
                {l}
              </p>
            ))}
            <div ref={logsEndRef} />
          </div>

          {/* Clips */}
          {job.clips.length > 0 && (
            <div className="space-y-3">
              <h2 className="font-semibold">Clips generados</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {job.clips.map((c) => (
                  <div key={c.filename} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                    <video
                      src={api.clipUrl(c.filename)}
                      controls
                      className="w-full aspect-[9/16] object-cover bg-black"
                    />
                    <div className="p-3 space-y-1">
                      <p className="text-sm font-medium line-clamp-1">{c.title}</p>
                      <p className="text-xs text-zinc-500 line-clamp-2">{c.hook}</p>
                      <a
                        href={api.clipUrl(c.filename)}
                        download={c.filename}
                        className="inline-block mt-2 text-xs bg-zinc-800 hover:bg-zinc-700 px-3 py-1 rounded-lg transition-colors"
                      >
                        Descargar
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProcessPage() {
  return (
    <Suspense>
      <ProcessContent />
    </Suspense>
  );
}
