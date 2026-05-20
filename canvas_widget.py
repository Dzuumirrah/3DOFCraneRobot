from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QThread, QMutex, pyqtSlot

import cv2
import time
from io import BytesIO
from urllib.parse import urlparse

import params

COLOR = params.COLORS
W_CANVAS, H_CANVAS = params.S_FIX_CANVAS
R_LIMITS_MIN, R_LIMITS_MAX = params.R_LIMITS
THETA_LIMITS_MIN, THETA_LIMITS_MAX = params.THETA_LIMITS

class IPWebCamThread(QThread):
    """
    Background thread untuk capture video dari IP Webcam APP (android).
    
    IP webcam dapat diakses dari URL seperti http://<IP_ADDRESS>:8080/video
    """
    frame_ready = pyqtSignal(object)

    def __init__(self, ip_address=params.IP_CAMERA_URL, port=8080):
        super().__init__()
        self.ip_address = ip_address
        self.port = port
        self.url = self._build_stream_url(ip_address, port)
        self.running = False
        self.cap = None

    @staticmethod
    def _build_stream_url(ip_address, port):
        base_url = str(ip_address).strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            base_url = f"http://{base_url}"
        if base_url.endswith("/video"):
            return base_url
        parsed = urlparse(base_url)
        if parsed.port is not None:
            return f"{base_url}/video"
        return f"{base_url}:{port}/video"

    def run(self):
        """Start streaming dari IP webcam."""
        try: 
            print(f"[IPWebcam]: Connecting to IP webcam at == {self.url} ==...")
            
            # Coba akses URL video stream untuk memastikan koneksi
            self.cap = cv2.VideoCapture(self.url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self.cap.isOpened():
                print("[IPWebcam]: Cannot open camera")
                return
            
            self.running = True
            print("[IPWebcam]: Camera thread started")

            frame_count = 0
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.flip(frame, 1)  # Mirror image
                    self.frame_ready.emit(frame)
                    time.sleep(0.010)  # ~100 FPS

                    frame_count += 1
                    if frame_count % 30 == 0:
                        print(f"[IPWebcam]: Received {frame_count} frames")
                else:
                    print("[IPWebcam]: Stream disconnected")
                    break
                
        except Exception as e:
            print(f"[IPWebcam]: Error in camera thread: {e}")
        finally:
            self.running = False
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            print("[IPWebcam]: Camera thread stopped")

    def stop(self):
        """Stop video capture."""
        self.running = False
        if self.cap is not None:
            self.cap.release()
        self.wait(1500)
                
    
class CraneCanvasWidget(QWidget):
    """
    Interactive vcanvas untuk crane workspace.
    Signal emitter saat user klik target.
    """
    target_clicked = pyqtSignal(float, float) # (cm, cm)

    # Workspace params (cm)
    WORKSPACE_CENTER_X = 0   # Center of semicircle (middle of workspace)
    WORKSPACE_CENTER_Y = 0    # Y = 0 at home level
    WORKSPACE_RADIUS_MIN = R_LIMITS_MIN
    WORKSPACE_RADIUS_MAX = R_LIMITS_MAX
    WORKSPACE_ARC_START_ANGLE = THETA_LIMITS_MIN   # degrees
    WORKSPACE_ARC_END_ANGLE = THETA_LIMITS_MAX   # degrees
    TASK_SPACE_RADIUS = 40     # Max reach radius
    # Visual params
    GRID_SPACING = 5
    MARGIN = 40


    def __init__(self):
        super().__init__()
        self.setFixedSize(W_CANVAS, H_CANVAS)
        self.setStyleSheet(f"background-color:{COLOR['DARKER_BLUE']}")
        self.setFocusPolicy(Qt.StrongFocus)

        # State (cm)
        self.crane_pos = (self.WORKSPACE_CENTER_X, self.WORKSPACE_CENTER_Y)
        self.target_pos = None
        self.home_pos = (self.WORKSPACE_CENTER_X, self.WORKSPACE_CENTER_Y)

        # Camera declaration
        self.show_camera = False
        self.camera_frame = None
        self.camera_thread = None
        self.camera_enabled = False

    @pyqtSlot(object)
    def _on_camera_frame(self, frame):
        """Receive frame dari camera thread."""
        self.camera_frame = frame.copy()
        self.update() # Triger repaint

    def mousePressEvent(self, event):
        """Tangkap klik user"""
        if event.button() == Qt.LeftButton:
            x_cm, y_cm = self._pixel_to_cartesian(event.x(), event.y())
            # Validasi jangkauan
            if self._is_in_workspace(x_cm, y_cm):
                self.set_target(x_cm, y_cm) 

    def _is_in_workspace(self, x_cm: float, y_cm: float) -> bool:
        """
        Validasi apakah click di dalam workspace
        Workspace = setengah lingkaran di kuadran 1 dan 2 dengan
        radius tertentu.
        """
        # Kondisi di bawah workspace (kuadran 3 dan 4)
        if y_cm < self.WORKSPACE_CENTER_Y:
            return False
        
        # jarak dari titik tengah
        dx = x_cm - self.WORKSPACE_CENTER_X
        dy = y_cm - self.WORKSPACE_CENTER_Y
        dist = (dx**2 + dy**2)**0.5

        return dist <= self.TASK_SPACE_RADIUS
        

    def _pixel_to_cartesian(self, px, py):
        """Konversi piksel ke kartesian (dalam cm)."""
        # Titik tengah 
        canvas_center_px = self.width() / 2
        canvas_center_py = self.height() - self.MARGIN

        # radius canvas
        canvas_radius_px = (self.width() - 2*self.MARGIN) / 2

        # Jarak titik dari tengah
        dx_px = px - canvas_center_px
        dy_py = canvas_center_py - py # Flip canvas agar meningkat ke bawah
        
        # Normalisasi ke koordinat workspace 
        x_cm = (dx_px / canvas_radius_px) * self.TASK_SPACE_RADIUS + self.WORKSPACE_CENTER_X
        y_cm = (dy_py / canvas_radius_px) * self.TASK_SPACE_RADIUS + self.WORKSPACE_CENTER_Y
        
        return x_cm, y_cm
    
    def _cartesian_to_pixel(self, x_cm, y_cm):
        """Konversi kartesian (cm) ke pixel untuk draw - semicircle workspace"""
        # Center and radius in pixels
        canvas_center_px = self.width() / 2
        canvas_center_py = self.height() - self.MARGIN
        canvas_radius_px = (self.width() - 2*self.MARGIN) / 2
 
        # Distance from workspace center
        dx_cm = x_cm - self.WORKSPACE_CENTER_X
        dy_cm = y_cm - self.WORKSPACE_CENTER_Y
 
        # Scale to pixels
        dx_px = (dx_cm / self.TASK_SPACE_RADIUS) * canvas_radius_px
        dy_px = (dy_cm / self.TASK_SPACE_RADIUS) * canvas_radius_px
 
        # Convert to pixel coordinates (flip Y back)
        px = canvas_center_px + dx_px
        py = canvas_center_py - dy_px
 
        return int(px), int(py)
    
    def set_target(self, x_cm, y_cm, emit_signal = True):
        """Set target dan emit signal."""
        self.target_pos = (x_cm, y_cm)
        if emit_signal:
            self.target_clicked.emit(x_cm, y_cm)
        self.update() # Triger repaint

    def set_crane_position(self, x_cm, y_cm):
        """Update posisi crane (dari feedback motor)"""
        self.crane_pos = (x_cm, y_cm)
        self.update()

    def paintEvent(self, event):
        """Render canvas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.show_camera and self.camera_frame is not None:
            self._draw_camera_background(painter)
        else:
            painter.fillRect(self.rect(), QColor(COLOR['DARKER_BLUE']))
        
        # Draw BG grid
        self._draw_grid(painter)

        # Draw reachable area (Circle)
        self._draw_workspace_limit(painter)

        # Draw crane position
        self._draw_crane(painter)

        # draw target point
        if self.target_pos:
            self._draw_target(painter)

        # Draw axes labels
        self._draw_labels(painter)

    def _draw_camera_background(self, painter):
        """Draw camera frame sebagai background."""
        if self.camera_frame is None:
            return
        
        # Convert OpenCV BGR to RGB
        rgb_frame = cv2.cvtColor(self.camera_frame, cv2.COLOR_BGR2RGB)
        
        # Resize frame untuk menyesuaikan dengan canvas
        h, w, ch = rgb_frame.shape
        widget_w, widget_h = self.width(), self.height()

        # jaga aspect ratio and cover the canvas
        scale = max(widget_w / w, widget_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        rgb_frame = cv2.resize(rgb_frame, (new_w, new_h))
        h, w, ch = rgb_frame.shape
        
        # Convert ke QImage
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qt_image)
        
        # center ke canvas
        pixmap_x = (widget_w - pixmap.width()) // 2
        pixmap_y = (widget_h - pixmap.height()) // 2

        painter.drawPixmap(pixmap_x, pixmap_y, pixmap)

    def _draw_grid(self, painter):
        """Draw grid lines"""
        pen = QPen(QColor(100, 100, 120), 0.5)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)

        # Radial lines (from center outward)
        for angle_deg in range(0, 180, 30):  # 0° to 180° every 30°
            import math
            angle_rad = math.radians(angle_deg)
            x_start = self.WORKSPACE_CENTER_X
            y_start = self.WORKSPACE_CENTER_Y
            x_end = self.WORKSPACE_CENTER_X + self.TASK_SPACE_RADIUS * math.cos(angle_rad)
            y_end = self.WORKSPACE_CENTER_Y + self.TASK_SPACE_RADIUS * math.sin(angle_rad)
            
            px1, py1 = self._cartesian_to_pixel(x_start, y_start)
            px2, py2 = self._cartesian_to_pixel(x_end, y_end)
            painter.drawLine(px1, py1, px2, py2)
 
        # Concentric circles (distance from center)
        canvas_center_px = self.width() / 2
        canvas_center_py = self.height() - self.MARGIN
        canvas_radius_px = (self.width() - 2*self.MARGIN) / 2
        
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        
        for r_cm in range(int(self.GRID_SPACING), int(self.TASK_SPACE_RADIUS)+1, int(self.GRID_SPACING)):
            radius_px = (r_cm / self.TASK_SPACE_RADIUS) * canvas_radius_px
            # Draw semicircle arc (only upper half)
            painter.drawArc(
                int(canvas_center_px - radius_px),
                int(canvas_center_py - radius_px),
                int(radius_px * 2),
                int(radius_px * 2),
                0, 180 * 16  # 180 degrees in 1/16ths
            )

    def _draw_workspace_limit(self, painter):
        """Draw reachable area (semicirle)."""
        canvas_center_px = self.width() / 2
        canvas_center_py = self.height() - self.MARGIN
        canvas_radius_px = (self.width() - 2*self.MARGIN) / 2
        
        pen = QPen(QColor(255, 100, 100), 1.5)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        
         # Draw max workspace radius.
        outer_radius_cm = self.WORKSPACE_RADIUS_MAX
        outer_radius_px = (outer_radius_cm / self.TASK_SPACE_RADIUS) * canvas_radius_px
        
        # Draw semicircle arc (upper half only, 0° to 180°)
        painter.drawArc(
            int(canvas_center_px - outer_radius_px),
            int(canvas_center_py - outer_radius_px),
            int(outer_radius_px * 2),
            int(outer_radius_px * 2),
            self.WORKSPACE_ARC_START_ANGLE, self.WORKSPACE_ARC_END_ANGLE * 16  # 180 degrees in 1/16ths
        )
         # Draw min workspace radius.
        inner_radius_cm = self.WORKSPACE_RADIUS_MIN
        inner_radius_px = (inner_radius_cm / self.TASK_SPACE_RADIUS) * canvas_radius_px
        
        painter.drawArc(
            int(canvas_center_px - inner_radius_px),
            int(canvas_center_py - inner_radius_px),
            int(inner_radius_px * 2),
            int(inner_radius_px * 2),
            self.WORKSPACE_ARC_START_ANGLE, self.WORKSPACE_ARC_END_ANGLE * 16
        )
        
        # Draw baseline (y=0)
        base_left_px, base_py = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X - self.TASK_SPACE_RADIUS, self.WORKSPACE_CENTER_Y)
        base_right_px, _ = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X + self.TASK_SPACE_RADIUS, self.WORKSPACE_CENTER_Y)
        painter.drawLine(base_left_px, base_py, base_right_px, base_py)
    
    def _draw_crane(self, painter):
        """Draw crane current position (end-effector)."""
        px, py = self._cartesian_to_pixel(*self.crane_pos)

        # End effector marker (circle)
        painter.setPen(QPen(QColor(0, 200, 100), 2))
        painter.setBrush(QBrush(QColor(0, 200, 100, 100)))
        painter.drawEllipse(px - 8, py - 8, 16, 16)

        # crosshair
        painter.setPen(QPen(QColor(0, 200, 100), 1))
        painter.drawLine(px - 12, py, px + 12, py)
        painter.drawLine(px, py - 12, px, py + 12)

    def _draw_target(self, painter):
        """draw target pont."""
        px, py = self._cartesian_to_pixel(*self.target_pos)

        # Target marker (square + cross)
        painter.setPen(QPen(QColor(255, 150, 0), 2))
        painter.setBrush(QBrush(Qt.NoBrush))
        painter.drawRect(px - 10, py - 10, 20, 20)

        painter.drawLine(px - 15, py, px + 15, py)
        painter.drawLine(px, py - 15, px, py + 15)

    def _draw_labels(self, painter):
        """draw axis labels."""
        font = QFont("Arial", 9)
        painter.setFont(font)
        painter.setPen(QColor(150, 150, 150))

        # Radius labels (concentric circles)
        for r_cm in range(int(self.GRID_SPACING), int(self.TASK_SPACE_RADIUS)+1, 15):
            px, py = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X + r_cm, self.WORKSPACE_CENTER_Y)
            painter.drawText(px, py - 15, 25, 15, Qt.AlignCenter, f"{r_cm}cm")
        
        # Center (home) marker
        home_px, home_py = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X, self.WORKSPACE_CENTER_Y)
        painter.setPen(QColor(100, 200, 100))
        painter.drawText(home_px - 20, home_py + 8, 40, 12, Qt.AlignCenter, "HOME")
        
        # Angle labels (0°, 45°, 90°, 135°, 180°)
        import math
        for angle_deg in [0, 45, 90, 135, 180]:
            r_marker = self.TASK_SPACE_RADIUS * 1.1  # Slightly outside
            angle_rad = math.radians(angle_deg)
            x_cm = self.WORKSPACE_CENTER_X + r_marker * math.cos(angle_rad)
            y_cm = self.WORKSPACE_CENTER_Y + r_marker * math.sin(angle_rad)
            px, py = self._cartesian_to_pixel(x_cm, y_cm)
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(px - 12, py - 8, 24, 15, Qt.AlignCenter, f"{angle_deg}°")
