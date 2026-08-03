# Generador de apuntes de clase

Aplicacion local para subir audios o videos de clases, transcribirlos con STT, y exportar:

- un apunte estructurado en texto
- un resumen breve
- la transcripcion limpia
- subtitulos en formato SRT

## Tecnologias

- Streamlit para la interfaz
- faster-whisper para la transcripcion
- ffmpeg para extraer audio de videos

## Requisitos

- Python 3.10 o superior
- ffmpeg instalado y disponible en PATH

En Windows podes instalar ffmpeg con `winget` o `choco`.

## Instalacion

Desde esta carpeta:

```bash
pip install -r requirements.txt
```

## Uso

Ejecutar la app:

```bash
streamlit run stt.py
```

Luego:

1. Elegi el modelo y el idioma desde la barra lateral.
2. Subi un audio o video de clase.
3. Tocá **Generar apunte**.
4. Descargá el `.txt` o el `.srt` resultante.

## Notas

- El modelo se descarga la primera vez que lo usas.
- `small` es el valor por defecto porque da un buen balance entre calidad y velocidad.
- Si elegis `cuda`, necesitas GPU compatible y una instalacion de Python que soporte esa aceleracion.
