"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Report = {
  id: string; title: string; url: string; published: string;
  views: number; retention_pct: number; avg_view_duration_s: number;
  watch_minutes: number; likes: number; shares: number; subs_gained: number;
};

function fmtDur(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(28);
  const [report, setReport] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await api.analytics(days);
      setReport(res.report as Report[]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar analytics");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const best = report[0];

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold mb-1">Analytics</h1>
          <p className="text-zinc-400 text-sm">Rendimiento de tus clips publicados en YouTube</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
          >
            <option value={7}>7 días</option>
            <option value={28}>28 días</option>
            <option value={90}>90 días</option>
          </select>
          <button onClick={load} disabled={loading} className="bg-zinc-800 hover:bg-zinc-700 text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50">
            {loading ? "Cargando..." : "Actualizar"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 text-center">
          <p className="text-zinc-400 text-sm mb-1">{error}</p>
          <p className="text-zinc-600 text-xs">Asegúrate de haber conectado YouTube con OAuth (scripts/setup_youtube.py)</p>
        </div>
      )}

      {/* Best performer */}
      {best && (
        <div className="bg-gradient-to-r from-red-950/40 to-zinc-900 border border-red-900/40 rounded-xl p-6">
          <p className="text-xs text-red-400 font-medium mb-2 uppercase tracking-wider">Mejor clip</p>
          <p className="font-semibold text-lg mb-3">{best.title}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div><p className="text-2xl font-bold text-red-400">{best.retention_pct}%</p><p className="text-xs text-zinc-500">Retención</p></div>
            <div><p className="text-2xl font-bold">{best.views.toLocaleString()}</p><p className="text-xs text-zinc-500">Vistas</p></div>
            <div><p className="text-2xl font-bold">{fmtDur(best.avg_view_duration_s)}</p><p className="text-xs text-zinc-500">Duración promedio</p></div>
            <div><p className="text-2xl font-bold">+{best.subs_gained}</p><p className="text-xs text-zinc-500">Suscriptores ganados</p></div>
          </div>
        </div>
      )}

      {/* Table */}
      {report.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-500 border-b border-zinc-800">
                <th className="text-left py-3 pr-4">Video</th>
                <th className="text-right py-3 px-3">Retención</th>
                <th className="text-right py-3 px-3">Vistas</th>
                <th className="text-right py-3 px-3">Avg dur.</th>
                <th className="text-right py-3 px-3">Likes</th>
                <th className="text-right py-3 pl-3">Subs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900">
              {report.map((r) => (
                <tr key={r.id} className="hover:bg-zinc-900/50 transition-colors">
                  <td className="py-3 pr-4">
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:text-red-400 transition-colors line-clamp-1">
                      {r.title}
                    </a>
                    <p className="text-xs text-zinc-600">{r.published}</p>
                  </td>
                  <td className="text-right py-3 px-3">
                    <span className={`font-medium ${r.retention_pct >= 50 ? "text-green-400" : r.retention_pct >= 30 ? "text-yellow-400" : "text-zinc-400"}`}>
                      {r.retention_pct}%
                    </span>
                  </td>
                  <td className="text-right py-3 px-3 text-zinc-300">{r.views.toLocaleString()}</td>
                  <td className="text-right py-3 px-3 text-zinc-400">{fmtDur(r.avg_view_duration_s)}</td>
                  <td className="text-right py-3 px-3 text-zinc-400">{r.likes.toLocaleString()}</td>
                  <td className="text-right py-3 pl-3 text-zinc-400">+{r.subs_gained}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
