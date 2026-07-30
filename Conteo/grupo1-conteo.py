import cv2
from ultralytics import YOLO

# =========================
# Cargar modelo YOLO
# =========================
modelo = YOLO("yolov8n.pt")  # Se descarga automáticamente

# =========================
# Abrir video
# =========================
video = cv2.VideoCapture("autos.mp4")

if not video.isOpened():
    print("Error al abrir el video")
    exit()

# =========================
# Variables de conteo
# =========================
contador_autos = 0
ids_contados = set()

# Línea virtual para contar
linea_y = 300

# =========================
# Procesar video
# =========================
while True:
    ret, frame = video.read()

    if not ret:
        break

    # Detectar y seguir objetos
    resultados = modelo.track(
        frame,
        persist=True,
        classes=[2, 3, 5, 7]  # auto, moto, bus, camión
    )

    # Dibujar línea de conteo
    cv2.line(frame, (0, linea_y), (frame.shape[1], linea_y), (0, 255, 255), 3)

    # Revisar detecciones
    if resultados[0].boxes.id is not None:

        cajas = resultados[0].boxes.xyxy.cpu().numpy()
        ids = resultados[0].boxes.id.cpu().numpy()

        for caja, obj_id in zip(cajas, ids):

            x1, y1, x2, y2 = map(int, caja)

            # Centro del vehículo
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            # Dibujar caja
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)

            # Dibujar centro
            cv2.circle(frame, (cx, cy), 5, (0,0,255), -1)

            # Mostrar ID
            cv2.putText(frame,
                        f"ID {int(obj_id)}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255,255,255),
                        2)

            # Contar si cruza la línea
            if cy > linea_y and obj_id not in ids_contados:
                contador_autos += 1
                ids_contados.add(obj_id)

    # Mostrar contador
    cv2.putText(frame,
                f"Autos: {contador_autos}",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0,255,255),
                3)

    cv2.imshow("Conteo de Autos", frame)

    # Salir con ESC
    tecla = cv2.waitKey(1)
    if tecla == 27:
        break

# =========================
# Liberar recursos
# =========================
video.release()
cv2.destroyAllWindows()

print(f"Total de autos contados: {contador_autos}")