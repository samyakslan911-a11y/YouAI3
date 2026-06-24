import argparse
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.core.pipeline import ContentPipeline
from src.utils.logger import get_logger

log = get_logger(__name__)

VALID_PLATFORMS = {"tiktok", "instagram", "youtube"}


def _cmd_process(args):
    pipeline = ContentPipeline(platforms=args.platforms, dry_run=args.dry_run)
    result = pipeline.run(args.source)

    if not result.success:
        log.error(f"Pipeline falló: {result.error}")
        sys.exit(1)

    print(f"\n✓ {len(result.clips)} clips generados:")
    for clip in result.clips:
        print(f"  {clip}")

    if result.publish_results:
        print("\nPublicaciones:")
        for pr in result.publish_results:
            icon = "✓" if pr.success else "✗"
            detail = pr.url if pr.success else pr.error
            print(f"  {icon} [{pr.platform}] {detail}")


def _cmd_analytics(args):
    from src.services import analytics

    report = analytics.get_report(days=args.days)
    if not report:
        print("Sin datos aún. Publica clips primero o amplía --days.")
        return

    top = report[: args.top]
    print(f"\nRendimiento últimos {args.days} días — top {len(top)} clips por retención\n")
    print(f"{'#':<3} {'Ret%':>5}  {'Vistas':>7}  {'AvgDur':>7}  {'Likes':>6}  {'Shares':>6}  Título")
    print("-" * 85)
    for i, v in enumerate(top, 1):
        dur = f"{v['avg_view_duration_s'] // 60}:{v['avg_view_duration_s'] % 60:02d}"
        print(
            f"{i:<3} {v['retention_pct']:>4.1f}%"
            f"  {v['views']:>7,}"
            f"  {dur:>7}"
            f"  {v['likes']:>6,}"
            f"  {v['shares']:>6,}"
            f"  {v['title'][:45]}"
        )

    best = top[0]
    print(f"\nMejor clip: {best['title']}")
    print(f"  Retención: {best['retention_pct']}%  |  Watch time: {best['watch_minutes']} min  |  Subs ganados: {best['subs_gained']}")
    print(f"  {best['url']}")


def _cmd_research(args):
    from src.services import researcher

    videos = researcher.search_outliers(
        query=args.query,
        max_results=args.max,
        min_outlier_ratio=args.ratio,
        language=args.lang,
        cc_only=args.cc,
    )

    if not videos:
        print("No se encontraron outliers con esos criterios. Prueba reducir --ratio.")
        sys.exit(1)

    print(f"\n{'#':<3} {'Ratio':>6}  {'Vistas':>10}  {'Canal avg':>10}  {'Duración':>8}  Título")
    print("-" * 90)
    for i, v in enumerate(videos, 1):
        dur = f"{v['duration_s'] // 60}:{v['duration_s'] % 60:02d}"
        print(
            f"{i:<3} {v['outlier_ratio']:>5.1f}x"
            f"  {v['views']:>10,}"
            f"  {v['channel_avg_views']:>10,}"
            f"  {dur:>8}"
            f"  {v['title'][:55]}"
        )
        print(f"     {v['url']}  — {v['channel_name']}  ({v['published']})")

    if args.run:
        try:
            choice = input(f"\n¿Cuál procesar? (1-{len(videos)}, Enter para cancelar): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not choice:
            return
        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(videos)):
                raise ValueError
        except ValueError:
            print(f"Número inválido. Elige entre 1 y {len(videos)}.")
            return

        selected = videos[idx]
        print(f"\nProcesando: {selected['title']}")
        print(f"  {selected['url']}\n")
        process_args = argparse.Namespace(
            source=selected["url"],
            platforms=list(VALID_PLATFORMS),
            dry_run=True,
        )
        _cmd_process(process_args)


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de contenido: genera clips virales y los publica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python -m src.core.cli process 'https://youtu.be/...' --dry-run\n"
            "  python -m src.core.cli research 'gaming reacción' --max 10\n"
            "  python -m src.core.cli research 'minecraft español' --ratio 5 --run\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # process (default)
    p_proc = sub.add_parser("process", help="Procesa un video y genera clips")
    p_proc.add_argument("source", help="URL de YouTube o ruta a archivo local")
    p_proc.add_argument(
        "--platforms", nargs="+", choices=sorted(VALID_PLATFORMS),
        default=list(VALID_PLATFORMS), metavar="PLATFORM",
    )
    p_proc.add_argument("--dry-run", action="store_true", help="Genera clips pero no publica")

    # analytics
    p_ana = sub.add_parser("analytics", help="Reportes de rendimiento de tus clips publicados")
    p_ana.add_argument("--days", type=int, default=28, help="Ventana de días (default: 28)")
    p_ana.add_argument("--top", type=int, default=10, help="Mostrar top N videos (default: 10)")

    # research
    p_res = sub.add_parser("research", help="Busca videos virales del nicho")
    p_res.add_argument("query", help='Término de búsqueda, ej: "gaming reacción"')
    p_res.add_argument("--max", type=int, default=10, help="Máximo de resultados (default: 10)")
    p_res.add_argument("--ratio", type=float, default=3.0,
                       help="Ratio mínimo vistas/promedio canal para ser outlier (default: 3.0)")
    p_res.add_argument("--lang", default="es", help="Idioma de búsqueda (default: es)")
    p_res.add_argument("--run", action="store_true",
                       help="Muestra resultados y pregunta cuál video procesar")
    p_res.add_argument("--cc", action="store_true",
                       help="Solo videos con licencia Creative Commons (sin copyright)")

    # backward compat: si el primer arg es una URL, tratarlo como "process"
    args, unknown = parser.parse_known_args()
    if args.command is None:
        # re-parse treating everything as "process"
        sys.argv.insert(1, "process")
        args = parser.parse_args()

    if args.command == "process":
        _cmd_process(args)
    elif args.command == "research":
        _cmd_research(args)
    elif args.command == "analytics":
        _cmd_analytics(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
