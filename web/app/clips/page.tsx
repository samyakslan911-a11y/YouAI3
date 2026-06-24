"use client";
import { useEffect, useState } from "react";
import { api, type Clip } from "@/lib/api";

export default function ClipsPage() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listClips().then((r) => { setClips(r.clips); setLoading(false); });
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-1">Clips</h1>
        <p className="text-zinc-400 text-sm">Todos los clips generados listos para publicar</p>
      </div>

      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-zinc-900 rounded-xl aspect-[9/16] animate-pulse" />
          ))}
        </div>
      )}

      {!loading && clips.length === 0 && (
        <div className="text-center py-20 text-zinc-500">
          <p className="text-lg mb-2">Sin clips aún</p>
          <p className="text-sm">Ve a <a href="/process" className="text-red-400 hover:underline">Procesar</a> para generar tu primer clip</p>
        </div>
      )}

      {clips.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {clips.map((c) => (
            <div key={c.filename} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden group hover:border-zinc-600 transition-colors">
              <video
                src={api.clipUrl(c.filename)}
                controls
                preload="metadata"
                className="w-full aspect-[9/16] object-cover bg-black"
              />
              <div className="p-3 space-y-2">
                <p className="text-xs text-zinc-400 line-clamp-2 leading-snug">{c.filename.replace(/_final\.mp4$/, "").replace(/_/g, " ")}</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-600">{c.size_mb} MB</span>
                  <a
                    href={api.clipUrl(c.filename)}
                    download={c.filename}
                    className="text-xs bg-zinc-800 hover:bg-zinc-700 px-3 py-1 rounded-lg transition-colors"
                  >
                    Descargar
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
