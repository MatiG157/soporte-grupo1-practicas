from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "auto"
SUPPORTED_LANGUAGES = [
	"auto",
	"es",
	"en",
	"pt",
	"fr",
	"it",
	"de",
	"ja",
	"ko",
	"zh",
]


@dataclass(frozen=True)
class Segment:
	start: float
	end: float
	text: str


@dataclass(frozen=True)
class TranscriptionResult:
	title: str
	source_name: str
	detected_language: str
	language_probability: float | None
	duration_seconds: float | None
	segments: list[Segment]
	transcript_text: str
	summary: str
	note: str
	srt: str


def is_video_file(path: Path) -> bool:
	return path.suffix.lower() in VIDEO_EXTENSIONS


def is_supported_media(path: Path) -> bool:
	return path.suffix.lower() in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def format_timestamp(seconds: float) -> str:
	total_milliseconds = max(0, int(round(seconds * 1000)))
	hours, remainder = divmod(total_milliseconds, 3_600_000)
	minutes, remainder = divmod(remainder, 60_000)
	secs, milliseconds = divmod(remainder, 1_000)
	return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_clock(seconds: float) -> str:
	total_seconds = max(0, int(seconds))
	hours, remainder = divmod(total_seconds, 3_600)
	minutes, secs = divmod(remainder, 60)
	if hours:
		return f"{hours:02d}:{minutes:02d}:{secs:02d}"
	return f"{minutes:02d}:{secs:02d}"


def compress_whitespace(text: str) -> str:
	return re.sub(r"\s+", " ", text).strip()


def clean_transcript_text(text: str) -> str:
	fillers = [
		r"\b(este|eh|emm|mmm|o sea|digamos|bueno)\b",
	]
	cleaned = text
	for pattern in fillers:
		cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\s+,", ",", cleaned)
	cleaned = re.sub(r"\s+\.", ".", cleaned)
	return compress_whitespace(cleaned)


def split_sentences(text: str) -> list[str]:
	parts = re.split(r"(?<=[.!?])\s+", text)
	return [part.strip() for part in parts if part.strip()]


def build_summary(segments: Iterable[Segment]) -> str:
	candidates: list[str] = []
	for segment in segments:
		sentence = clean_transcript_text(segment.text)
		if len(sentence) < 25:
			continue
		candidates.append(sentence)
		if len(candidates) == 3:
			break

	if candidates:
		return " ".join(candidates)

	return "No se detecto suficiente contenido para generar un resumen automatico."


def group_segments(segments: list[Segment], max_gap_seconds: float = 10.0, max_group_chars: int = 750) -> list[list[Segment]]:
	groups: list[list[Segment]] = []
	current_group: list[Segment] = []

	for segment in segments:
		if not current_group:
			current_group.append(segment)
			continue

		last_segment = current_group[-1]
		group_text = " ".join(item.text for item in current_group)
		should_split = (segment.start - last_segment.end) > max_gap_seconds or len(group_text) > max_group_chars

		if should_split:
			groups.append(current_group)
			current_group = [segment]
		else:
			current_group.append(segment)

	if current_group:
		groups.append(current_group)

	return groups


def build_note(title: str, source_name: str, detected_language: str, duration_seconds: float | None, segments: list[Segment]) -> str:
	summary = build_summary(segments)
	groups = group_segments(segments)

	key_points: list[str] = []
	for group in groups:
		first_text = clean_transcript_text(group[0].text)
		if not first_text:
			continue
		key_points.append(first_text)
		if len(key_points) == 6:
			break

	transcript_lines: list[str] = []
	for idx, group in enumerate(groups, start=1):
		start_time = format_clock(group[0].start)
		end_time = format_clock(group[-1].end)
		paragraph = clean_transcript_text(" ".join(segment.text for segment in group))
		transcript_lines.append(f"Bloque {idx} [{start_time} - {end_time}]\n{paragraph}")

	duration_label = format_clock(duration_seconds or 0.0) if duration_seconds is not None else "No disponible"

	note_sections = [
		f"Título: {title}",
		f"Archivo: {source_name}",
		f"Idioma detectado: {detected_language}",
		f"Duración estimada: {duration_label}",
		"",
		"Resumen breve",
		summary,
		"",
		"Puntos clave",
	]

	if key_points:
		note_sections.extend(f"- {point}" for point in key_points)
	else:
		note_sections.append("- No se pudieron extraer puntos clave")

	note_sections.extend([
		"",
		"Apunte estructurado",
		*transcript_lines,
	])

	return "\n".join(note_sections).strip()


def build_srt(segments: list[Segment]) -> str:
	blocks: list[str] = []
	for index, segment in enumerate(segments, start=1):
		text = clean_transcript_text(segment.text)
		if not text:
			continue
		blocks.append(
			"\n".join(
				[
					str(index),
					f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}",
					text,
				]
			)
		)
	return "\n\n".join(blocks)


def build_plain_transcript(segments: list[Segment]) -> str:
	paragraphs = [clean_transcript_text(segment.text) for segment in segments if clean_transcript_text(segment.text)]
	return "\n\n".join(textwrap.fill(paragraph, width=90) for paragraph in paragraphs)


def extract_audio_if_needed(source_path: Path, temp_dir: Path) -> Path:
	if not is_video_file(source_path):
		return source_path

	if shutil.which("ffmpeg") is None:
		raise RuntimeError("ffmpeg no esta instalado o no esta disponible en PATH.")

	output_path = temp_dir / f"{source_path.stem}_audio.wav"
	command = [
		"ffmpeg",
		"-y",
		"-i",
		str(source_path),
		"-vn",
		"-ac",
		"1",
		"-ar",
		"16000",
		"-sample_fmt",
		"s16",
		str(output_path),
	]
	subprocess.run(command, check=True, capture_output=True)
	return output_path


def get_compute_type(device: str) -> str:
	return "float16" if device == "cuda" else "int8"


@lru_cache(maxsize=8)
def load_whisper_model(model_size: str, device: str):
	from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]

	compute_type = get_compute_type(device)
	return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_media(
	media_path: Path,
	title: str,
	model_size: str,
	language: str,
	device: str,
	progress_message: Callable[[str], None] | None = None,
) -> TranscriptionResult:
	with tempfile.TemporaryDirectory() as temp_dir_name:
		temp_dir = Path(temp_dir_name)
		if progress_message is not None:
			progress_message("Preparando archivo multimedia...")
		audio_path = extract_audio_if_needed(media_path, temp_dir)
		if progress_message is not None:
			progress_message(f"Cargando modelo {model_size} en {device}...")
		model = load_whisper_model(model_size=model_size, device=device)

		language_arg = None if language == DEFAULT_LANGUAGE else language
		if progress_message is not None:
			progress_message("Transcribiendo audio...")
		segments_iter, info = model.transcribe(
			str(audio_path),
			language=language_arg,
			vad_filter=True,
			beam_size=5,
			word_timestamps=False,
		)

		segments = [
			Segment(start=float(segment.start), end=float(segment.end), text=segment.text.strip())
			for segment in segments_iter
			if segment.text.strip()
		]

	detected_language = getattr(info, "language", language_arg or DEFAULT_LANGUAGE)
	language_probability = getattr(info, "language_probability", None)
	duration_seconds = getattr(info, "duration", None)

	transcript_text = build_plain_transcript(segments)
	if progress_message is not None:
		progress_message("Armando resumen y apunte...")
	summary = build_summary(segments)
	note = build_note(
		title=title,
		source_name=media_path.name,
		detected_language=detected_language,
		duration_seconds=duration_seconds,
		segments=segments,
	)
	srt = build_srt(segments)

	return TranscriptionResult(
		title=title,
		source_name=media_path.name,
		detected_language=detected_language,
		language_probability=language_probability,
		duration_seconds=duration_seconds,
		segments=segments,
		transcript_text=transcript_text,
		summary=summary,
		note=note,
		srt=srt,
	)


def write_uploaded_file(uploaded_file, destination_dir: Path) -> Path:
	suffix = Path(uploaded_file.name).suffix.lower() or ".bin"
	output_path = destination_dir / f"upload{suffix}"
	output_path.write_bytes(uploaded_file.getbuffer())
	return output_path


def render_app() -> None:
	import streamlit as st  # pyright: ignore[reportMissingImports]

	st.set_page_config(
		page_title="Apunte de Clases STT",
		page_icon="mic",
		layout="wide",
		initial_sidebar_state="expanded",
	)

	st.title("Generador de apuntes de clase")
	st.caption("Subi un audio o video y obtene transcripcion, resumen, apunte estructurado y exportacion a SRT.")

	with st.sidebar:
		st.header("Configuracion")
		model_size = st.selectbox(
			"Modelo",
			options=["tiny", "base", "small", "medium", "large-v3"],
			index=2,
			help="Modelos mas grandes mejoran la calidad pero tardan mas.",
		)
		language = st.selectbox(
			"Idioma",
			options=SUPPORTED_LANGUAGES,
			index=0,
			help="Usa auto si no estas seguro del idioma.",
		)
		device = st.selectbox(
			"Dispositivo",
			options=["cpu", "cuda"],
			index=0,
			help="cuda requiere GPU compatible y la libreria correspondiente.",
		)
		note_title = st.text_input("Titulo del apunte", value="Apunte de clase")

	uploaded_file = st.file_uploader(
		"Subi un archivo de audio o video",
		type=["mp3", "wav", "m4a", "aac", "ogg", "flac", "opus", "mp4", "mov", "mkv", "webm", "avi", "m4v"],
	)

	if uploaded_file is None:
		st.info("Subi un archivo para empezar. El proyecto funciona localmente y no necesita API keys.")
		st.stop()

	if not is_supported_media(Path(uploaded_file.name)):
		st.error("El archivo subido no parece ser un formato soportado.")
		st.stop()

	col_left, col_right = st.columns([1, 1])
	with col_left:
		st.write(f"**Archivo:** {uploaded_file.name}")
		st.write(f"**Tipo:** {uploaded_file.type or 'desconocido'}")
	with col_right:
		st.write("**Salida:** resumen, apunte estructurado, texto plano y SRT")

	generate_button = st.button("Generar apunte", type="primary")

	if not generate_button:
		st.stop()

	with tempfile.TemporaryDirectory() as temp_dir_name:
		temp_dir = Path(temp_dir_name)
		media_path = write_uploaded_file(uploaded_file, temp_dir)

		if not media_path.exists():
			st.error("No se pudo guardar el archivo subido.")
			st.stop()

		with st.spinner("Transcribiendo y armando el apunte..."):
			status = st.empty()
			try:
				result = transcribe_media(
					media_path=media_path,
					title=note_title.strip() or "Apunte de clase",
					model_size=model_size,
					language=language,
					device=device,
					progress_message=lambda message: status.info(message),
				)
			except subprocess.CalledProcessError as exc:
				st.error("No se pudo procesar el archivo multimedia con ffmpeg.")
				if exc.stderr:
					st.code(exc.stderr.decode("utf-8", errors="ignore"), language="text")
				st.stop()
			except Exception as exc:  # pragma: no cover - surfaced in UI
				st.error(f"Ocurrio un error al transcribir: {exc}")
				st.stop()
			status.empty()

	metric_cols = st.columns(4)
	metric_cols[0].metric("Idioma detectado", result.detected_language)
	metric_cols[1].metric("Segmentos", len(result.segments))
	metric_cols[2].metric("Duracion", format_clock(result.duration_seconds or 0.0) if result.duration_seconds else "N/A")
	metric_cols[3].metric("Modelo", model_size)

	tab_resumen, tab_apunte, tab_texto, tab_srt = st.tabs(["Resumen", "Apunte", "Texto limpio", "SRT"])

	with tab_resumen:
		st.subheader("Resumen breve")
		st.write(result.summary)
		if result.language_probability is not None:
			st.caption(f"Confianza del idioma detectado: {result.language_probability:.2f}")

	with tab_apunte:
		st.subheader("Apunte estructurado")
		st.text_area("Salida", value=result.note, height=500)

	with tab_texto:
		st.subheader("Transcripcion limpia")
		st.text_area("Texto", value=result.transcript_text, height=500)

	with tab_srt:
		st.subheader("Subtitulos SRT")
		st.text_area("SRT", value=result.srt, height=500)

	st.divider()
	st.download_button(
		label="Descargar apunte (.txt)",
		data=result.note.encode("utf-8"),
		file_name=f"{sanitize_filename(result.title)}.txt",
		mime="text/plain",
	)
	st.download_button(
		label="Descargar subtitulos (.srt)",
		data=result.srt.encode("utf-8"),
		file_name=f"{sanitize_filename(result.title)}.srt",
		mime="application/x-subrip",
	)


def sanitize_filename(value: str) -> str:
	value = value.strip().lower()
	value = re.sub(r"[^a-z0-9._-]+", "_", value)
	value = re.sub(r"_+", "_", value).strip("._-")
	return value or "apunte_clase"


def main() -> None:
	render_app()


if __name__ == "__main__":
	main()
