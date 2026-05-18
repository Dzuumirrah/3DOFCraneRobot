from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

import params

COLOR = params.COLORS

class CraneCanvasWidget(QWidget):
    """
    Interactive vcanvas untuk crane workspace.
    Signal emitter saat user klik target.
    """
    target_clicked = pyqtSignal(float, float) # (cm, cm)

    # Workspace params (cm)
    WORKSPACE_X_MIN, WORKSPACE_X_MAX = 0, 50
    WORKSPACE_Y_MIN, WORKSPACE_Y_MAX = 0, 50

    # Visual params
    GRID_SPACING = 5
    MARGIN = 40

    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 500)
        self.setStyleSheet(f"background-color:{COLOR['DARKER_BLUE']}")
        self.setFocusPolicy(Qt.StrongFocus)

        # State (cm)
        self.crane_pos = (0,0)
        self.target_pos = None
        self.radius_limit = 45

    def mousePressEvent(self, event):
        """Tangkap klik user"""
        if event.button() == Qt.LeftButton:
            x_cm, y_cm = self._pixel_to_cartesian(event.x(), event.y())
            self.set_target(x_cm, y_cm)

    def _pixel_to_cartesian(self, px, py):
        """Konversi piksel ke kartesian (dalam cm)."""
        # Hitung skala pixel -> cm
        canvas_width = self.width() - 2 * self.MARGIN
        canvas_height = self.height() - 2 * self.MARGIN

        scale_x = (self.WORKSPACE_X_MAX - self.WORKSPACE_X_MIN) / canvas_width
        scale_y = (self.WORKSPACE_Y_MAX - self.WORKSPACE_Y_MIN) / canvas_height

        x_cm = (px - self.MARGIN) * scale_x + self.WORKSPACE_X_MIN
        y_cm = (self.height() - py - self.MARGIN) * scale_y + self.WORKSPACE_Y_MIN

        # Clamp ke workspace
        x_cm = max(self.WORKSPACE_X_MIN, min (self.WORKSPACE_X_MAX, x_cm))
        y_cm = max(self.WORKSPACE_Y_MIN, min (self.WORKSPACE_Y_MAX, y_cm))

        return x_cm, y_cm
    
    def __cartesian_to_pixel(self, x_cm, y_cm):
        """Konversi kartesian (cm) ke pixel untuk draw"""
        # Hitung skala pixel -> cm
        canvas_width = self.width() - 2 * self.MARGIN
        canvas_height = self.height() - 2*self.MARGIN

        scale_x = canvas_width / (self.WORKSPACE_X_MAX - self.WORKSPACE_X_MIN) 
        scale_y = canvas_height / (self.WORKSPACE_Y_MAX - self.WORKSPACE_Y_MIN)

        px = (x_cm - self.WORKSPACE_X_MIN) * scale_x + self.MARGIN
        py = self.height() - ((y_cm - self.WORKSPACE_Y_MIN) * scale_y + self.MARGIN)

        return int(px), int(py)
    
    def set_target(self, x_cm, y_cm):
        """Set target dan emit signal."""
        self.target_pos = (x_cm, y_cm)
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

        # Vertical line
        for x_cm in range(
            self.WORKSPACE_X_MIN,
            self.WORKSPACE_X_MAX + 1,
            self.GRID_SPACING
        ):
            px1, py1 = self.__cartesian_to_pixel(x_cm, self.WORKSPACE_Y_MIN)
            px2, py2 = self.__cartesian_to_pixel(x_cm, self.WORKSPACE_Y_MAX)
            painter.drawLine(px1, py1, px2, py2)

        # Horizontal line
        for y_cm in range(
            self.WORKSPACE_Y_MIN,
            self.WORKSPACE_Y_MAX + 1,
            self.GRID_SPACING
        ):
            px1, py1 = self.__cartesian_to_pixel(self.WORKSPACE_X_MIN, y_cm)
            px2, py2 = self.__cartesian_to_pixel(self.WORKSPACE_X_MAX, y_cm)
            painter.drawLine(px1, py1, px2, py2)

    def _draw_workspace_limit(self, painter):
        """Draw reachable area (cirle)."""
        cx, cy = self.__cartesian_to_pixel(25, 25)  # center
        radius_px = int((self.radius_limit / 50) * ( self.width() - 2 *self.MARGIN) / 2)
        pen = QPen(QColor(255, 100, 100), 1.5)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(cx - radius_px, cy - radius_px, radius_px * 2, radius_px * 2)

    def _draw_crane(self, painter):
        """Draw crane current position (end-effector)."""
        px, py = self.__cartesian_to_pixel(*self.crane_pos)

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
        px, py = self.__cartesian_to_pixel(*self.target_pos)

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

        # X- axis labels
        for x_cm in range(0, self.WORKSPACE_X_MAX + 1, 10):
            px, _ = self.__cartesian_to_pixel(x_cm, self.WORKSPACE_Y_MIN)
            painter.drawText(px - 10, self.height() - 10, 20, 15, 
                             Qt.AlignCenter, f"{x_cm}")
            
        for y_cm in range(0, self.WORKSPACE_Y_MAX + 1, 10):
            _, py = self.__cartesian_to_pixel(self.WORKSPACE_X_MIN, y_cm)
            painter.drawText(10, py - 8, 25, 15, 
                             Qt.AlignCenter, f"{y_cm}")
            
        # Axis names
        painter.drawText(self.width() - 40, self.height() - 10, 30, 15,
                         Qt.AlignCenter, "X (cm)")
        painter.drawText(10, 15, 25, 15,
                         Qt.AlignCenter, "Y (cm)")
        