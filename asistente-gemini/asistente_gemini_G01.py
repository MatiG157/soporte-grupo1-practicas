"""
Asistente de voz con Gemini
----------------------------
Flujo:
1. Escucha por el micrófono (speech_recognition -> STT).
2. Al detectar la palabra de activación, abre una "conversación" que
   queda activa: podés seguir preguntando sin repetir la palabra clave.
3. Si pasan 30 segundos sin que digas nada, la conversación vuelve a
   standby (hay que decir la palabra de activación de nuevo).
4. Mientras la conversación está activa, Gemini mantiene memoria de
   todo lo que se habló (se usa un `chat` con historial, no llamadas
   sueltas a generate_content).
5. Convierte cada respuesta de Gemini a audio (gTTS) y la reproduce.

Requisitos (instalar con pip):
    pip install SpeechRecognition gTTS pygame google-genai pyaudio

Nota sobre PyAudio:
- En Windows: pip install pyaudio suele funcionar directo.
- En Linux: puede requerir antes -> sudo apt-get install portaudio19-dev
- En Mac: brew install portaudio

Configurá tu API key de Gemini como variable de entorno (NUNCA la
hardcodees en el código):
    export GEMINI_API_KEY="tu_api_key_aqui"      (Linux/Mac)
    setx GEMINI_API_KEY "tu_api_key_aqui"        (Windows)
"""

import os
import tempfile

import speech_recognition as sr
from gtts import gTTS
import pygame
from google import genai
from google.genai import errors as genai_errors


# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_MODEL_FALLBACKS = list(dict.fromkeys([
    GEMINI_MODEL,
    "gemini-2.5-flash-lite",
    "gemini-1.5-flash",
]))

IDIOMA_STT = "es-AR"                     # idioma para el reconocimiento de voz
IDIOMA_TTS = "es"                        # idioma para la síntesis de voz
PALABRA_ACTIVACION = "hola asistente"    # frase de activación (en minúsculas)
TIMEOUT_STANDBY_SEG = 30                 # segundos sin hablar -> vuelve a standby
FRASES_SALIR = ("salir", "terminar", "chau")

client = genai.Client(api_key=GEMINI_API_KEY)
pygame.mixer.init()


# ------------------------------------------------------------------
# 1) Escucha corta en loop, solo para detectar la palabra de activación
# ------------------------------------------------------------------
def esperar_palabra_activacion(reconocedor, fuente):
    """
    Escucha frases cortas de forma continua (sin bloquear para siempre)
    y devuelve True apenas detecta la palabra de activación.
    Ignora silencios y errores de reconocimiento sin cortar el loop.
    """
    while True:
        try:
            # phrase_time_limit corta la escucha a los 3s para no quedar
            # esperando de más en cada vuelta del loop.
            audio = reconocedor.listen(
                fuente, timeout=None, phrase_time_limit=3
            )
        except sr.WaitTimeoutError:
            continue

        try:
            texto = reconocedor.recognize_google(audio, language=IDIOMA_STT)
        except (sr.UnknownValueError, sr.RequestError):
            continue

        texto = texto.lower().strip()
        if PALABRA_ACTIVACION in texto:
            return True


# ------------------------------------------------------------------
# 2) Crear un chat con memoria, probando modelos de fallback
# ------------------------------------------------------------------
def crear_chat_gemini():
    """
    Intenta crear una sesión de chat (con historial propio) probando
    los modelos de la lista de fallback en orden. Devuelve una tupla
    (chat, nombre_modelo) o (None, None) si ninguno funcionó.
    """
    for modelo in GEMINI_MODEL_FALLBACKS:
        try:
            chat = client.chats.create(model=modelo)
            print(f"Conversación iniciada con el modelo: {modelo}")
            return chat, modelo
        except genai_errors.ClientError as exc:
            print(f"No se pudo iniciar chat con {modelo}: {exc}")

    print("Gemini no está disponible con ningún modelo de la lista.")
    return None, None


# ------------------------------------------------------------------
# 3) Enviar un mensaje al chat activo (mantiene memoria automáticamente)
# ------------------------------------------------------------------
def preguntar_a_gemini_chat(chat, modelo_activo, texto):
    if chat is None:
        return (
            "No pude iniciar la conversación con Gemini. Revisá la cuota "
            "de la API, la facturación o la variable GEMINI_MODEL."
        )

    try:
        respuesta = chat.send_message(texto)
        print(f"Gemini ({modelo_activo}): {respuesta.text}")
        return respuesta.text
    except genai_errors.ClientError as exc:
        print(f"Error consultando a Gemini ({modelo_activo}): {exc}")
        return (
            "No pude consultar Gemini ahora mismo. Revisá la cuota de la API, "
            "la facturación o la variable GEMINI_MODEL."
        )


# ------------------------------------------------------------------
# 4) Convertir la respuesta a voz y reproducirla (TTS)
# ------------------------------------------------------------------
def hablar(texto):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as archivo_temp:
        ruta_audio = archivo_temp.name

    tts = gTTS(text=texto, lang=IDIOMA_TTS)
    tts.save(ruta_audio)

    pygame.mixer.music.load(ruta_audio)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.music.unload()
    os.remove(ruta_audio)


# ------------------------------------------------------------------
# Bucle principal
# ------------------------------------------------------------------
def main():
    print("=== Asistente de voz con Gemini ===")
    print(f"Decí '{PALABRA_ACTIVACION}' para activarlo.")
    print(
        f"Una vez activado, la conversación queda abierta: podés seguir "
        f"preguntando sin repetir la palabra clave."
    )
    print(
        f"Si pasan {TIMEOUT_STANDBY_SEG} segundos sin que digas nada, vuelve "
        f"a standby (y se pierde la memoria de esa conversación)."
    )
    print("Decí 'salir', 'terminar' o 'chau' para cerrar el programa.\n")

    reconocedor = sr.Recognizer()

    with sr.Microphone() as fuente:
        print("Calibrando ruido ambiente, esperá un segundo...")
        reconocedor.adjust_for_ambient_noise(fuente, duration=1)
        print(f"Listo. Esperando que digas '{PALABRA_ACTIVACION}'...\n")

        while True:
            # Standby: espera la palabra de activación
            esperar_palabra_activacion(reconocedor, fuente)
            print(f"\n¡Te escucho! (activado con '{PALABRA_ACTIVACION}')")

            # Al activarse, se crea una conversación nueva con memoria propia
            chat_actual, modelo_activo = crear_chat_gemini()

            conversacion_activa = True
            while conversacion_activa:
                print(
                    f"Escuchando... (si no decís nada en {TIMEOUT_STANDBY_SEG}s "
                    f"vuelvo a standby)"
                )
                try:
                    audio = reconocedor.listen(
                        fuente, timeout=TIMEOUT_STANDBY_SEG, phrase_time_limit=15
                    )
                    texto_usuario = reconocedor.recognize_google(
                        audio, language=IDIOMA_STT
                    )
                    print(f"Vos dijiste: {texto_usuario}")
                except sr.WaitTimeoutError:
                    print(
                        f"\nPasaron {TIMEOUT_STANDBY_SEG}s sin actividad. "
                        f"Volviendo a standby...\n"
                    )
                    conversacion_activa = False
                    continue
                except sr.UnknownValueError:
                    print("No entendí el audio, seguís en la conversación.")
                    continue
                except sr.RequestError as e:
                    print(f"Error con el servicio de reconocimiento: {e}")
                    continue

                if texto_usuario.lower().strip() in FRASES_SALIR:
                    print("Cerrando el asistente...")
                    return

                respuesta_gemini = preguntar_a_gemini_chat(
                    chat_actual, modelo_activo, texto_usuario
                )
                hablar(respuesta_gemini)

            print(f"Esperando que digas '{PALABRA_ACTIVACION}'...")


if __name__ == "__main__":
    main()