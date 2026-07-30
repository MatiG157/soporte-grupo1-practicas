import cv2
import numpy as np

camera_matrix = np.array([[800, 0, 320],
                          [0, 800, 240],
                          [0, 0, 1]], dtype=np.float32)
dist_coeffs = np.zeros((5, 1), dtype=np.float32)

marker_length = 0.05 
half_l = marker_length / 2

pyramid_points = np.array([
    [-half_l,  half_l, 0],               
    [ half_l,  half_l, 0],               
    [ half_l, -half_l, 0],               
    [-half_l, -half_l, 0],               
    [ 0,       0,      -marker_length]   
], dtype=np.float32)

marker_3d_edges = np.array([
    [-half_l,  half_l, 0],
    [ half_l,  half_l, 0],
    [ half_l, -half_l, 0],
    [-half_l, -half_l, 0]
], dtype=np.float32)

dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
parameters = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(dictionary, parameters)

cap = cv2.VideoCapture(0)
window_name = 'Realidad Aumentada - ArUco'
cv2.namedWindow(window_name)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is not None:
        for i in range(len(ids)):
            success, rvec, tvec = cv2.solvePnP(
                marker_3d_edges, corners[i], camera_matrix, dist_coeffs
            )

            if success:

                img_points, _ = cv2.projectPoints(
                    pyramid_points, rvec, tvec, camera_matrix, dist_coeffs
                )
                pts = np.int32(img_points).reshape(-1, 2)

                overlay = frame.copy()

                cv2.fillConvexPoly(overlay, np.array([pts[0], pts[1], pts[4]]), (0, 0, 255))
                cv2.fillConvexPoly(overlay, np.array([pts[1], pts[2], pts[4]]), (0, 255, 0))
                cv2.fillConvexPoly(overlay, np.array([pts[2], pts[3], pts[4]]), (255, 0, 0))
                cv2.fillConvexPoly(overlay, np.array([pts[3], pts[0], pts[4]]), (0, 255, 255))

                cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

                cv2.line(frame, tuple(pts[0]), tuple(pts[1]), (255, 255, 255), 2)
                cv2.line(frame, tuple(pts[1]), tuple(pts[2]), (255, 255, 255), 2)
                cv2.line(frame, tuple(pts[2]), tuple(pts[3]), (255, 255, 255), 2)
                cv2.line(frame, tuple(pts[3]), tuple(pts[0]), (255, 255, 255), 2)
                for j in range(4):
                    cv2.line(frame, tuple(pts[j]), tuple(pts[4]), (255, 255, 255), 2)

                
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, 0.03)

    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF
   
    if key == ord('q') or key == ord('Q') or key == 27:
        break

    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break

cap.release()
cv2.destroyAllWindows()

for _ in range(10):
    cv2.waitKey(1)
