from dataclasses import dataclass, field
from pathlib import Path

from src.services import downloader, transcriber, analyzer, editor, publisher
from src.utils.logger import get_logger

log = get_logger(__name__)

DEFAULT_PLATFORMS = ["tiktok", "instagram", "youtube"]


@dataclass
class PipelineResult:
    source: str
    clips: list[Path] = field(default_factory=list)
    publish_results: list[publisher.PublisherResult] = field(default_factory=list)
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and bool(self.clips)


class ContentPipeline:
    def __init__(self, platforms: list[str] | None = None, dry_run: bool = False):
        self.platforms = platforms or DEFAULT_PLATFORMS
        self.dry_run = dry_run

    def run(self, source: str) -> PipelineResult:
        result = PipelineResult(source=source)
        try:
            log.info(f"=== Pipeline iniciado: {source} ===")

            video_path = downloader.download(source)
            log.info(f"Video: {video_path.name}")

            video_duration = editor.get_video_duration(video_path)
            log.info(f"Duración: {video_duration:.1f}s")

            segments_raw = transcriber.transcribe(video_path)
            log.info(f"Transcripción: {len(segments_raw)} segmentos")

            video_title = video_path.stem.replace("_", " ")
            viral_segments = analyzer.analyze(segments_raw, video_title)
            log.info(f"Momentos virales: {len(viral_segments)}")

            for i, seg in enumerate(viral_segments):
                try:
                    clip_path = editor.process_segment(video_path, seg, i, video_duration)
                    result.clips.append(clip_path)

                    if not self.dry_run:
                        pub_results = publisher.publish_all(clip_path, seg, self.platforms)
                        result.publish_results.extend(pub_results)
                        for pr in pub_results:
                            status = "OK" if pr.success else f"ERROR: {pr.error}"
                            log.info(f"  [{pr.platform}] {status}")
                    else:
                        log.info(f"  dry-run: clip guardado en {clip_path}")
                except Exception as e:
                    log.error(f"  Clip {i+1} omitido: {e}")

            if not result.clips:
                result.error = "Ningún clip se generó correctamente"

            log.info(f"=== Pipeline completado: {len(result.clips)} clips ===")

        except Exception as e:
            result.error = str(e)
            log.error(f"Pipeline error: {e}")

        return result
