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
    pyqtSlot,
    QTimer
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
from serial_comm import CraneSerialComm, SerialConfig

import params

COLOR = params.COLORS
W_MAIN, H_MAIN = params.S_FIX_MAIN
COM_PORT = params.COM_PORT
BAUD_RATE = params.BAUD_RATE

class MainWindow(QMainWindow):
    def __init__ (self):
        super().__init__()
        self.setWindowTitle("Robot Crane 3-DOF GUI")
        self.setMinimumSize(W_MAIN, H_MAIN)
        self._build_layout()

        self.target = None

        self.limits = JointLimits(
            theta_min=-180, theta_max=180,
            r_min=15, r_max=45,
            h_min=0, h_max=50
        )
        self.ik = CraneKinematics(self.limits)

        self.serial_config = SerialConfig(
            port=COM_PORT, 
            baudrate=BAUD_RATE,
            timeout=1
        )
        
        self.serial_comm = CraneSerialComm(self.serial_config)
        self._setup_serial_callbacks()

        # Tr auto connect 
        self._attempt_serial_connection()

        # Auto-idle timer setelah 5 detik
        self.idle_timer = QTimer()
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._on_idle_timeout)
        self.IDLE_TIMEOUT_MS = 5000

    def _setup_serial_callbacks(self):
        """Setup callback untuk serial events """
        self.serial_comm.set_callbacks(
            on_feedback = self._on_serial_feedback,
            on_error = self._on_serial_error,
            on_connected = self._on_serial_connected,
            on_disconnected = self._on_serial_disconnected
        )

    def _attempt_serial_connection(self):
        """Coba connect ke serial saat startup"""
        if self.serial_comm.connect(self.serial_comm.config.port):
            print(f"[MAIN] Connected to serial port {COM_PORT} at {BAUD_RATE} baud.")
        else:
            print(f"[MAIN] Failed to connect to serial port {COM_PORT}. Running in offline mode.")
            self.panel.set_status("ERROR", f"Serial connection failed on {COM_PORT}")
    
    @pyqtSlot(str)
    def _on_serial_feedback(self, feedback: str):
        """Handle feedback dari serial (contoh: status update)"""
        print(f"[SERIAL FEEDBACK] {feedback}")

        # Parse common responses 
        if feedback == "DONE":
            self.panel.set_status("DONE", "Action completed")
        elif feedback == "IDLE":
            self.panel.set_status("IDLE", "Ready for command")
        elif feedback.startswith("ERROR"):
            self.panel.set_status("ERROR", feedback)
        elif feedback.startswith("POS"):
            # position feedback
            try:
                parts = feedback.split(',')
                if len(parts) >= 4:
                    theta = float(parts[1])
                    r = float(parts[2])
                    h = float(parts[3])

                    # update canvas
                    import math
                    x_cm = 25 + r * math.cos(math.radians(theta))
                    y_cm = r * math.sin(math.radians(theta))
                    self.canvas.set_crane_position(x_cm, y_cm)
            except(ValueError, IndexError):
                print(f"[SERIAL FEEDBACK] Failed to parse position feedback: {feedback}")

    @pyqtSlot(str)
    def _on_serial_error(self, error_msg: str):
        """Handle serial errors"""
        print(f"[SERIAL ERROR] {error_msg}")
        self.panel.set_status("ERROR", f"Serial error: {error_msg}")

    @pyqtSlot()
    def _on_serial_connected(self):
        """Handle serial connection established"""
        print(f"[SERIAL] Connection established.")
        self.panel.set_status("IDLE", "Serial connected, ready for command")

    @pyqtSlot()
    def _on_serial_disconnected(self):
        """Handle serial disconnection"""
        print(f"[SERIAL] Disconnected.")
        self.panel.set_status("ERROR", "Serial disconnected")

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
            self._start_idle_timer(1500)

        return result.theta_deg, result.r_cm, result.h_cm
    
    @pyqtSlot()
    def _on_pick(self):
        """Handle PICK command"""
        if not self.target:
            self.panel.set_status("ERROR", "No target set")
            return
        
        # Ambil target terakhir yang diklik
        x_cm, y_cm = self.target
        
        # Hitung IK untuk target
        theta_deg, r_cm, h_cm = self._calculate_ik(x_cm, y_cm)
        
        self.panel.set_status("MOVING", f"Moving to {x_cm:.1f}, {y_cm:.1f} to PICK")
        self._start_idle_timer()
        
        success = self.serial_comm.send_move_command(
            theta_deg = theta_deg,
            r_cm = r_cm,
            h_cm = h_cm,
            magnet_on = True
        )

        if not success:
            print(f"[MAIN] Failed to send PICK command to serial.")
            self.panel.set_status("ERROR", "Failed to send PICK command")
            self._start_idle_timer(1500)
        

    @pyqtSlot()
    def _on_place(self):
        """Handle PLACE command"""    
        self.panel.set_status("MOVING", "Placing object...")
        self._start_idle_timer()

        if self.target:
            # taruh ke target terakhir yang diklik
            x_cm, y_cm = self.target
        else:
            # jika tidak ada target, taruh di lokasi yang sama
            x_cm, y_cm = self.canvas.crane_pos
        
        theta_deg, r_cm, h_cm = self._calculate_ik(x_cm, y_cm)

        # kirim ke serial
        sucsess = self.serial_comm.send_move_command(
            theta_deg = theta_deg,
            r_cm = r_cm,
            h_cm = h_cm,
            magnet_on = False
        )
        if not sucsess:
            print(f"[MAIN] Failed to send PLACE command to serial.")
            self.panel.set_status("ERROR", "Failed to send PLACE command")
            self._start_idle_timer(1500)

    @pyqtSlot()
    def _on_home(self):
        """Handle HOME command"""
        self.panel.set_status("MOVING", "Going to HOME...")
        self.target = None
        self.canvas.set_target(self.canvas.home_pos[0], self.canvas.home_pos[1], emit_signal=False)
        
        self._start_idle_timer()
        
        # Kirim command HOME ke serial
        success = self.serial_comm.send_home_command()

        if not success:
            print(f"[MAIN] Failed to send HOME command to serial.")
            self.panel.set_status("ERROR", "Failed to send HOME command")
            self._start_idle_timer(1500)
    @pyqtSlot()
    def _on_estop(self):
        """Handle E-STOP command"""
        self.panel.set_status("ERROR", "EMERGENCY STOPPED")
        self.panel.enable_commands(False)
        self.idle_timer.stop()

        # Kirim command E-STOP ke serial
        self.serial_comm.send_estop_command()
        print(f"[MAIN] Emergency Stop activated!")

    @pyqtSlot()
    def _on_idle_timeout(self):
        """Auto return IDLE setelah timeout"""
        self.panel.set_status("IDLE", "Ready for command")
        self.panel.enable_commands(True)
        print("[Timer] Auto-idle timeout - kembali ke IDLE")

    def _start_idle_timer(self, timeMS=None):
        """Start hitung mundur ke auto-idle"""
        if not timeMS:
            self.idle_timer.start(self.IDLE_TIMEOUT_MS)
            return
        self.idle_timer.start(timeMS)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_() )
