from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont

import params

COLOR = params.COLORS
INDICATOR_COLOR = params.INDICATOR_COLOR

class ControlPanel(QWidget):
    """Control panel dengan buttons dan status displat"""

    # Signal untuk command ke craen
    pick_pressed = pyqtSignal()     # Ambil 
    place_pressed = pyqtSignal()    # Lepas
    home_pressed = pyqtSignal()     # Go to home (0,0)
    estop_pressed = pyqtSignal()    # Emergency Stop

    # tombol untuk aktivasi kamera
    camera_toggle = pyqtSignal(bool)  # True = aktifkan kamera, False = matikan kamera
    # tombol untuk ubah IP kamera
    change_ip_pressed = pyqtSignal()  # Tekan untuk ubah IP kamera

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {COLOR['DARKER_BLUE']}; color: white")
        self._build_layout()

        # State tracking
        self.current_status = "IDLE"
        self.last_target = None
        self.is_picked = False
        self.is_placed = False

    def _build_layout(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        # === STATUS SECTION ===
        status_group = self._build_status_section()
        main_layout.addWidget(status_group)

        # === COMMAND BUTTONS ===
        cmd_group = self._build_command_section()
        main_layout.addWidget(cmd_group)

        # === INFO SECTION ===
        info_group = self._build_info_section()
        main_layout.addWidget(info_group)

        main_layout.addStretch()

    def _build_status_section(self):
        """Status indikator + state display"""
        group = QGroupBox("Status")
        group.setStyleSheet(self._groupbox_style())
        layout = QVBoxLayout()

        # Status light (colored circle)
        status_layout = QHBoxLayout()
        self.status_light = QLabel("●")
        self.status_light.setFont(QFont("Arial", 24))
        self.status_light.setAlignment(Qt.AlignCenter)
        self.status_light.setFixedSize(40, 40)
        self._update_status_light("IDLE")

        status_text_layout = QVBoxLayout()
        self.status_label = QLabel("IDLE")
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.status_detail = QLabel("Ready for command")
        self.status_detail.setFont(QFont('Arial', 10))
        self.status_detail.setStyleSheet(f"color: {COLOR['GRAY']}")

        status_text_layout.addWidget(self.status_label)
        status_text_layout.addWidget(self.status_detail)

        status_layout.addWidget(self.status_light)
        status_layout.addLayout(status_text_layout)
        status_layout.addStretch()

        layout.addLayout(status_layout)
        group.setLayout(layout)
        self.update()
        return group
    
    def _build_command_section(self):
        """Command buttons."""
        group = QGroupBox("Commands")
        group.setStyleSheet(self._groupbox_style())
        layout = QGridLayout()
        layout.setSpacing(10)

        # Pick button
        self.btn_pick = QPushButton("PICK")
        self.btn_pick.setFixedHeight(50)
        self.btn_pick.setStyleSheet(self._button_style(COLOR["GREEN"]))
        self.btn_pick.clicked.connect(self._on_pick)
        layout.addWidget(self.btn_pick, 0, 0)
    
    
        # Place button
        self.btn_place = QPushButton("PLACE")
        self.btn_place.setFixedHeight(50)
        self.btn_place.setStyleSheet(self._button_style(COLOR["RED"]))
        self.btn_place.clicked.connect(self._on_place)
        layout.addWidget(self.btn_place, 0, 1)
    
        # home button
        self.btn_home = QPushButton("HOME")
        self.btn_home.setFixedHeight(50)
        self.btn_home.setStyleSheet(self._button_style(COLOR["BLUE"]))
        self.btn_home.clicked.connect(self._on_home)
        layout.addWidget(self.btn_home, 1, 0)
    
        # E-stop button
        self.btn_estop = QPushButton("E-STOP")
        self.btn_estop.setFixedHeight(50)
        self.btn_estop.setStyleSheet(self._button_style(COLOR["DARK_RED"], True))
        self.btn_estop.clicked.connect(self._on_estop)
        layout.addWidget(self.btn_estop, 1, 1)

        # camera toggle button
        self.btn_camera = QPushButton("CAMERA")
        self.btn_camera.setCheckable(True)
        self.btn_camera.setFixedHeight(50)
        self.btn_camera.setStyleSheet(self._button_style(COLOR["LIGHT_BLUE"]))
        self.btn_camera.toggled.connect(self._on_camera_toggle)
        layout.addWidget(self.btn_camera, 2, 0, 1, 2)

        # ubah IP adress kamera
        self.btn_change_ip = QPushButton("Change Camera IP")
        self.btn_change_ip.setFixedHeight(40)
        self.btn_change_ip.setStyleSheet(self._button_style(COLOR["LIGHT_BLUE"]))
        self.btn_change_ip.clicked.connect(self._on_change_camera_ip)
        layout.addWidget(self.btn_change_ip, 3, 0, 1, 2)

        group.setLayout(layout)
        self.update()
        return group
    
    def _build_info_section(self):
        """Display target info"""
        group = QGroupBox("Target Info")
        group.setStyleSheet(self._groupbox_style())
        layout = QVBoxLayout()

        # Target coordinates
        self.info_target = QLabel("No target set")
        self.info_target.setFont(QFont("Courier", 10))
        self.info_target.setStyleSheet(f"color: {COLOR['ORANGE']}")
        
        # Joint angles
        self.info_joints = QLabel("θ: — | r: — | h: —")
        self.info_joints.setFont(QFont("Courier", 10))
        self.info_joints.setStyleSheet(f"color: {COLOR['PURPLE']}")

        layout.addWidget(QLabel("Target:"))
        layout.addWidget(self.info_target)
        layout.addWidget(QLabel("Joints:"))
        layout.addWidget(self.info_joints)

        group.setLayout(layout)
        self.update()
        return group


    # === STYLING ===
    def _groupbox_style(self):
        return f"""
        QGroupBox {{
            border: 2px solid {COLOR['LIGHT_BLUE']};
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
            color: {COLOR['LIGHTER_BLUE']}      
        }}
        QGroupBox::title{{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px
            color: {COLOR['DARK_BLUE']}
        }}
        """
    def _button_style(self, bg_color, emergency=False):
        border_color = COLOR["RED"] if emergency else COLOR['DARKER_BLUE']
        return f"""
        QPushButton {{
            background-color: {bg_color};
            color: white;
            border: 2px solid {border_color};
            border-radius: 5px;
            font-weight: bold;
            font-size: 12px;
            padding: 5px;
        }}
        QPushButton:hover {{
            background-color: {self._lighten_color(bg_color)};
        }}
        QPushButton:pressed {{
            background-color: {self._darken_color(bg_color)};
        }}
        QPushButton:disabled {{
            background-color: {COLOR['DARKER_GRAY']};
            color: {COLOR['GRAY']};
        }}
        """
    
    @staticmethod
    def _lighten_color(hex_color):
        """Lighten color by 20%."""
        hex_color = hex_color.lstrip("#")
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(min(255, int(c * 1.2)) for c in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    @staticmethod
    def _darken_color(hex_color):
        """Darken color by 30%."""
        hex_color = hex_color.lstrip("#")
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(int(c * 0.7) for c in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    
    def _update_status_light(self, status):
        """Update status indicator color."""
        colors = {
            "IDLE": INDICATOR_COLOR['IDLE'],      # Blue
            "MOVING": INDICATOR_COLOR['MOVING'],    # Orange
            "DONE": INDICATOR_COLOR['DONE'],      # Green
            "ERROR": INDICATOR_COLOR['ERROR'],     # Red
            "HOMED": INDICATOR_COLOR['HOMED'],     # Blue
        }
        color = colors.get(status, COLOR['GRAY'])
        self.status_light.setStyleSheet(f"color: {color};")
        
    # === COMMAND HANDLERS ===
    
    def _on_pick(self):
        """Handle PICK command."""
        self.set_status("MOVING", "Picking up...")
        self.pick_pressed.emit()
        if self.is_picked and self.last_target:
            self.set_status("ERROR", "Already holding an object!")
        else:
            self.is_picked = True
            self.is_placed = False
    
    def _on_place(self):
        """Handle PLACE command."""
        self.set_status("MOVING", "Placing down...")
        self.place_pressed.emit()
        if self.is_placed:
            self.set_status("ERROR", "No object to place!")
        else:
            self.is_placed = True
            self.is_picked = False

    def _on_home(self):
        """Handle HOME command."""
        self.set_status("MOVING", "Going to home...")
        self.home_pressed.emit()
        self.is_placed = False
        self.is_picked = False
    
    def _on_estop(self):
        """Handle E-STOP."""
        self.set_status("ERROR", "EMERGENCY STOPPED!")
        self.estop_pressed.emit()
        self.is_placed = False
        self.is_picked = False
    
    def _on_camera_toggle(self):
        """Handle camera toggle."""
        is_checked = self.btn_camera.isChecked()
        if is_checked:
            self.btn_camera.setText("CAMERA ON")
            self.btn_camera.setStyleSheet(self._button_style(COLOR["GREEN"]))
            self.camera_toggle.emit(True)
        else:
            self.btn_camera.setText("CAMERA OFF")
            self.btn_camera.setStyleSheet(self._button_style(COLOR["LIGHT_BLUE"]))
            self.camera_toggle.emit(False)

    def _on_change_camera_ip(self):
        """Handle change camera IP button click."""
        self.set_status("IDLE", "Changing camera IP...")
        self.change_ip_pressed.emit()
    # === PUBLIC METHODS ===
    
    def set_status(self, status, detail=""):
        """Update status display."""
        self.current_status = status
        self.status_label.setText(status)
        self.status_detail.setText(detail)
        self._update_status_light(status)
    
    def set_target_info(self, x_cm, y_cm):
        """Display target coordinates."""
        self.last_target = (x_cm, y_cm)
        self.info_target.setText(f"X: {x_cm:.1f} cm  |  Y: {y_cm:.1f} cm")
    
    def set_joint_info(self, theta_deg, r_cm, h_cm):
        """Display calculated joint angles."""
        self.info_joints.setText(
            f"θ: {theta_deg:.1f}° | r: {r_cm:.1f} cm | h: {h_cm:.1f} cm"
        )
    
    def enable_commands(self, enabled=True):
        """Enable/disable command buttons."""
        self.btn_pick.setEnabled(enabled)
        self.btn_place.setEnabled(enabled)
        self.btn_home.setEnabled(enabled)

    def is_place_enabled(self):
        """Check if PLACE command should be enabled."""
        return self.is_picked


        