from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

import params

COLOR = params.COLORS
W_CANVAS, H_CANVAS = params.S_FIX_CANVAS

class CraneCanvasWidget(QWidget):
    """
    Interactive vcanvas untuk crane workspace.
    Signal emitter saat user klik target.
    """
    target_clicked = pyqtSignal(float, float) # (cm, cm)

    # Workspace params (cm)
    WORKSPACE_CENTER_X = 0   # Center of semicircle (middle of workspace)
    WORKSPACE_CENTER_Y = 0    # Y = 0 at home level
    WORKSPACE_RADIUS = 45     # Max reach radius
    WORKSPACE_Y_MAX = 45      # Upper limit of workspace

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

        return dist <= self.WORKSPACE_RADIUS
        

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
        x_cm = (dx_px / canvas_radius_px) * self.WORKSPACE_RADIUS + self.WORKSPACE_CENTER_X
        y_cm = (dy_py / canvas_radius_px) * self.WORKSPACE_RADIUS + self.WORKSPACE_CENTER_Y
        
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
        dx_px = (dx_cm / self.WORKSPACE_RADIUS) * canvas_radius_px
        dy_px = (dy_cm / self.WORKSPACE_RADIUS) * canvas_radius_px
 
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
            x_end = self.WORKSPACE_CENTER_X + self.WORKSPACE_RADIUS * math.cos(angle_rad)
            y_end = self.WORKSPACE_CENTER_Y + self.WORKSPACE_RADIUS * math.sin(angle_rad)
            
            px1, py1 = self._cartesian_to_pixel(x_start, y_start)
            px2, py2 = self._cartesian_to_pixel(x_end, y_end)
            painter.drawLine(px1, py1, px2, py2)
 
        # Concentric circles (distance from center)
        canvas_center_px = self.width() / 2
        canvas_center_py = self.height() - self.MARGIN
        canvas_radius_px = (self.width() - 2*self.MARGIN) / 2
        
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        
        for r_cm in range(int(self.GRID_SPACING), int(self.WORKSPACE_RADIUS)+1, int(self.GRID_SPACING)):
            radius_px = (r_cm / self.WORKSPACE_RADIUS) * canvas_radius_px
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
        
        # Draw semicircle arc (upper half only, 0° to 180°)
        painter.drawArc(
            int(canvas_center_px - canvas_radius_px),
            int(canvas_center_py - canvas_radius_px),
            int(canvas_radius_px * 2),
            int(canvas_radius_px * 2),
            0, 180 * 16  # 180 degrees in 1/16ths
        )
        
        # Draw baseline (y=0)
        base_left_px, base_py = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X - self.WORKSPACE_RADIUS, self.WORKSPACE_CENTER_Y)
        base_right_px, _ = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X + self.WORKSPACE_RADIUS, self.WORKSPACE_CENTER_Y)
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
        for r_cm in range(int(self.GRID_SPACING), int(self.WORKSPACE_RADIUS)+1, 15):
            px, py = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X + r_cm, self.WORKSPACE_CENTER_Y)
            painter.drawText(px, py - 15, 25, 15, Qt.AlignCenter, f"{r_cm}cm")
        
        # Center (home) marker
        home_px, home_py = self._cartesian_to_pixel(self.WORKSPACE_CENTER_X, self.WORKSPACE_CENTER_Y)
        painter.setPen(QColor(100, 200, 100))
        painter.drawText(home_px - 20, home_py + 8, 40, 12, Qt.AlignCenter, "HOME")
        
        # Angle labels (0°, 45°, 90°, 135°, 180°)
        import math
        for angle_deg in [0, 45, 90, 135, 180]:
            r_marker = self.WORKSPACE_RADIUS * 1.1  # Slightly outside
            angle_rad = math.radians(angle_deg)
            x_cm = self.WORKSPACE_CENTER_X + r_marker * math.cos(angle_rad)
            y_cm = self.WORKSPACE_CENTER_Y + r_marker * math.sin(angle_rad)
            px, py = self._cartesian_to_pixel(x_cm, y_cm)
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(px - 12, py - 8, 24, 15, Qt.AlignCenter, f"{angle_deg}°")