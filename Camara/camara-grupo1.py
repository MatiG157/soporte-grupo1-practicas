import cv2
import time
import os
import re
from pathlib import Path

# --- Configuración ---
# Directorios para guardar los archivos
BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "capturas" / "videos"
FOTOS_DIR = BASE_DIR / "capturas" / "fotos"

# --- Clase Principal de la Cámara ---
class Camara:
    def __init__(self):
        # Inicializar la captura de video
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara. Asegúrate de que esté conectada.")

        # Obtener dimensiones del video
        self.ancho = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.alto = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30 # Usar 30 fps si la cámara no lo reporta

        # Estado de la aplicación
        self.grabando = False
        self.video_writer = None
        self.temporizador_activo = False
        self.tiempo_fin_temporizador = 0
        self.estado_actual = "Presiona 'R' para grabar, 'F' para foto, 'T' para temporizador o 'Q' para salir."

        # Crear directorios si no existen
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        FOTOS_DIR.mkdir(parents=True, exist_ok=True)

    def _generar_ruta_archivo(self, carpeta: Path, prefijo: str, extension: str) -> Path:
        """Genera una ruta de archivo con un índice numérico secuencial."""
        patron = re.compile(rf"^{re.escape(prefijo)}_(\d+)\.{re.escape(extension)}$")
        max_indice = 0
        for ruta in carpeta.iterdir():
            coincidencia = patron.match(ruta.name)
            if coincidencia:
                max_indice = max(max_indice, int(coincidencia.group(1)))
        return carpeta / f"{prefijo}_{max_indice + 1:03d}.{extension}"

    def iniciar_grabacion(self):
        if self.grabando:
            return
        
        ruta_video = self._generar_ruta_archivo(VIDEOS_DIR, "video", "mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(str(ruta_video), fourcc, self.fps, (self.ancho, self.alto))
        
        if not self.video_writer.isOpened():
            self.estado_actual = "Error: No se pudo iniciar la grabación."
            return

        self.grabando = True
        self.estado_actual = f"Grabando en {ruta_video.name}"

    def detener_grabacion(self):
        if not self.grabando:
            return
        
        self.grabando = False
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        self.estado_actual = "Grabación detenida y guardada."

    def tomar_foto(self, frame_espejado):
        if self.grabando or self.temporizador_activo:
            return
            
        ruta_foto = self._generar_ruta_archivo(FOTOS_DIR, "foto", "jpg")
        cv2.imwrite(str(ruta_foto), frame_espejado)
        self.estado_actual = f"Foto guardada en {ruta_foto.name}"

    def iniciar_temporizador(self):
        if self.grabando or self.temporizador_activo:
            return
        
        self.temporizador_activo = True
        self.tiempo_fin_temporizador = time.time() + 3.5 # 3.5 segundos de cuenta regresiva
        self.estado_actual = "Iniciando temporizador para foto..."

    def _dibujar_ui(self, frame):
        """Dibuja todos los elementos de la interfaz en el frame."""
        # Efecto espejo para que se vea más natural
        frame_espejado = cv2.flip(frame, 1)

        # Indicador de grabación
        if self.grabando:
            cv2.circle(frame_espejado, (30, 35), 10, (0, 0, 255), -1) # Círculo rojo
            cv2.putText(frame_espejado, "REC", (50, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # Lógica y dibujo del temporizador
        if self.temporizador_activo:
            tiempo_restante = self.tiempo_fin_temporizador - time.time()
            if tiempo_restante > 0:
                texto_timer = str(int(tiempo_restante) + 1)
                # Dibuja el número grande en el centro
                tamaño_texto, _ = cv2.getTextSize(texto_timer, cv2.FONT_HERSHEY_SIMPLEX, 5, 10)
                pos_x = (self.ancho - tamaño_texto[0]) // 2
                pos_y = (self.alto + tamaño_texto[1]) // 2
                cv2.putText(frame_espejado, texto_timer, (pos_x, pos_y), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 255, 255), 10)
            else:
                self.temporizador_activo = False
                self.tomar_foto(frame_espejado) 

        # Barra de estado inferior
        cv2.rectangle(frame_espejado, (0, self.alto - 50), (self.ancho, self.alto), (0, 0, 0), -1)
        cv2.putText(frame_espejado, self.estado_actual, (10, self.alto - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Instrucciones
        texto_controles = "R: Grabar | F: Foto | T: Timer | Q: Salir"
        cv2.putText(frame_espejado, texto_controles, (10, self.alto - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        return frame_espejado

    def ejecutar(self):
        """Bucle principal de la aplicación."""
        while True:
            ret, frame = self.cap.read()
            if not ret:
                self.estado_actual = "Error: No se pudo leer el frame de la cámara."
                time.sleep(1)
                continue

            # Grabar el frame original (sin espejo) si se está grabando
            if self.grabando and self.video_writer:
                self.video_writer.write(frame)

            # Dibujar la UI y obtener el frame para mostrar
            frame_para_mostrar = self._dibujar_ui(frame)

            # Mostrar la ventana
            cv2.imshow("Cámara", frame_para_mostrar)

            # Manejar entrada del teclado
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord('q'):
                break
            elif tecla == ord('r'):
                if self.grabando:
                    self.detener_grabacion()
                else:
                    self.iniciar_grabacion()
            elif tecla == ord('f'):
                self.tomar_foto(frame_para_mostrar)
            elif tecla == ord('t'):
                self.iniciar_temporizador()
        
        # Limpieza final
        self.limpiar()

    def limpiar(self):
        """Libera todos los recursos."""
        if self.grabando:
            self.detener_grabacion()
        self.cap.release()
        cv2.destroyAllWindows()
        print("Aplicación de cámara cerrada limpiamente.")

# --- Punto de Entrada ---
if __name__ == "__main__":
    try:
        app = Camara()
        app.ejecutar()
    except Exception as e:
        print(f"Ocurrió un error: {e}")
