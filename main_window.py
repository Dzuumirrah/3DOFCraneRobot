import sys
import math
from PyQt5.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QWidget,
    QHBoxLayout, 
    QVBoxLayout,
)
from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    QPoint,
    pyqtSlot
)
from PyQt5.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QFont
)

from canvas_widget import CraneCanvasWidget
from control_panel import ControlPanel
from kinematics import CraneKinematics, JointLimits

import params

COLOR = params.COLORS
W_MAIN, H_MAIN = params.S_FIX_MAIN

class MainWindow(QMainWindow):
    def __init__ (self):
        super().__init__()
        self.setWindowTitle("Robot Crane 3-DOF GUI")
        self.setMinimumSize(W_MAIN, H_MAIN)
        self._build_layout()

        self.target = None

        self.limits = JointLimits(
            theta_min=-180, theta_max=180,
            r_min=0, r_max=45,
            h_min=0, h_max=50
        )
        self.ik = CraneKinematics(self.limits)

    def _build_layout(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setSpacing(10)
        root_layout.setContentsMargins(10, 10, 10, 10)

        # Kiri: Canvas area
        self.canvas = CraneCanvasWidget()
        self.canvas.target_clicked.connect(self._on_target_clicked)

        # Kanan: Panel area
        self.panel = ControlPanel()
        self.panel.pick_pressed.connect(self._on_pick)
        self.panel.place_pressed.connect(self._on_place)
        self.panel.home_pressed.connect(self._on_home)
        self.panel.estop_pressed.connect(self._on_estop)
        
        root_layout.addWidget(self.canvas, 3)
        root_layout.addWidget(self.panel, 1)

    @pyqtSlot(float, float)
    def _on_target_clicked(self, x_cm, y_cm):
        """User klik target di canvas"""
        self.target = (x_cm, y_cm)

        # Update control panel
        self.panel.set_target_info(x_cm, y_cm)

        # Calulate IK (placeholder)
        theta_deg, r_cm, h_cm = self._calculate_ik(x_cm, y_cm)
        self.panel.set_joint_info(theta_deg, r_cm, h_cm)

        print(f"Target: ({x_cm:.1f}, {y_cm:.1f}) → θ={theta_deg:.1f}°, r={r_cm:.1f}cm, h={h_cm:.1f}cm")
        
        # enable commands
        self.panel.enable_commands(True)

    def _calculate_ik(self, x_cm, y_cm, h_cm=20):
        """
        Calculate inverse kinematics using proper solver.
        
        Menggunakan CraneKinematics module dengan:
        - Proper IK calculation
        - Workspace validation
        - Joint constraints
        - Error handling
        """
        # theta_rad = math.atan2(y_cm, x_cm)
        # theta_deg = math.degrees(theta_rad)
        # r_cm = math.sqrt(x_cm**2 + y_cm**2)
        result = self.ik.calculate(x_cm, y_cm, h_cm)

        # handle error
        if not result.is_valid:
            print(f"IK Warning {result.error_msg}")
            self.panel.set_status("ERROR", result.error_msg)

        return result.theta_deg, result.r_cm, result.h_cm
    
    @pyqtSlot()
    def _on_pick(self):
        """Handle PICK command"""
        if not self.target:
            self.panel.set_status("ERROR", "No target set")
            return
        
        self.panel.set_status("MOVING", "Moving to target...")
        x_cm, y_cm = self.target
        # TODO: send command to crane via serial
        print(f"PICK command: move to({x_cm:.1f}, {y_cm:.1f})")

        

    @pyqtSlot()
    def _on_place(self):
        """Handle PLACE command"""    
        self.panel.set_status("MOVING", "Placing object...")
        # TODO: send command to crane via serial
        print(f"PLACE command: release magnet")

        
    @pyqtSlot()
    def _on_home(self):
        """Handle HOME command"""
        self.panel.set_status("MOVING", "Going to HOME...")
        self.target = None
        self.canvas.set_target(0, 0, emit_signal=False)
        # TODO: send command to crane via serial
        print(f"HOME command: move to(0, 0)")

    @pyqtSlot()
    def _on_estop(self):
        """Handle E-STOP command"""
        self.panel.set_status("ERROR", "EMERGENCY STOPPED")
        self.panel.enable_commands(False)
        # TODO: send EMERGENCY STOP  via serial
        print(f"E-STOP activated")
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_() )
