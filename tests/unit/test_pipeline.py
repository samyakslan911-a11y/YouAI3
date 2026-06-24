from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.pipeline import ContentPipeline, PipelineResult
from src.services.publisher import PublisherResult


FAKE_TRANSCRIPT = [
    {"text": "Hola bienvenidos al canal", "start": 0.0, "end": 3.5},
    {"text": "Hoy vamos a hablar de productividad", "start": 3.5, "end": 8.0},
    {"text": "El secreto es hacer una sola cosa a la vez", "start": 8.0, "end": 13.0},
]

FAKE_SEGMENTS = [
    {
        "start": 8.0,
        "end": 13.0,
        "title": "El secreto de la productividad",
        "hook": "¿Quieres ser más productivo? 🚀 #productividad #tips",
        "platforms": ["tiktok", "instagram", "youtube"],
    }
]


@patch("src.services.downloader.download", return_value=Path("tmp/test_video.mp4"))
@patch("src.services.transcriber.transcribe", return_value=FAKE_TRANSCRIPT)
@patch("src.services.analyzer.analyze", return_value=FAKE_SEGMENTS)
@patch("src.services.editor.process_segment", return_value=Path("output/test_clip_final.mp4"))
def test_pipeline_dry_run(mock_editor, mock_analyzer, mock_transcriber, mock_downloader):
    pipeline = ContentPipeline(platforms=["tiktok"], dry_run=True)
    result = pipeline.run("https://youtube.com/watch?v=test")

    assert result.success
    assert len(result.clips) == 1
    assert result.publish_results == []
    mock_downloader.assert_called_once()
    mock_transcriber.assert_called_once()
    mock_analyzer.assert_called_once()
    mock_editor.assert_called_once()


@patch("src.services.downloader.download", return_value=Path("tmp/test_video.mp4"))
@patch("src.services.transcriber.transcribe", return_value=FAKE_TRANSCRIPT)
@patch("src.services.analyzer.analyze", return_value=FAKE_SEGMENTS)
@patch("src.services.editor.process_segment", return_value=Path("output/test_clip_final.mp4"))
@patch("src.services.publisher.publish_all", return_value=[
    PublisherResult("tiktok", True, url="https://tiktok.com/@test/video/123")
])
def test_pipeline_with_publish(mock_pub, mock_editor, mock_analyzer, mock_transcriber, mock_dl):
    pipeline = ContentPipeline(platforms=["tiktok"], dry_run=False)
    result = pipeline.run("https://youtube.com/watch?v=test")

    assert result.success
    assert len(result.clips) == 1
    assert len(result.publish_results) == 1
    assert result.publish_results[0].success


@patch("src.services.downloader.download", side_effect=FileNotFoundError("video.mp4 no existe"))
def test_pipeline_handles_download_error(mock_dl):
    pipeline = ContentPipeline(dry_run=True)
    result = pipeline.run("archivo_inexistente.mp4")

    assert not result.success
    assert "no existe" in result.error


def test_pipeline_result_success_flag():
    result = PipelineResult(source="test")
    assert not result.success

    result.clips.append(Path("clip.mp4"))
    assert result.success

    result.error = "algo falló"
    assert not result.success
