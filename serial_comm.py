"""
Serial Communication Module
Robot Crane 3-DOF

Handles communication to ESP32 microcontroller via USB Serial.
Protocol: Newline-delimited JSON messages.
"""

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import serial
import serial.tools.list_ports


@dataclass
class SerialConfig:
    """Serial port configuration."""

    port: str = "COM7"
    baudrate: int = 115200
    timeout: float = 1.0
    write_timeout: float = 1.0
    use_feedback: bool = True


class CraneSerialComm:
    """
    Serial communication handler untuk Robot Crane.

    Features:
    - Non-blocking TX/RX dengan threading
    - Command queue management
    - JSON feedback parsing
    - Connection state tracking
    """

    def __init__(self, config: Optional[SerialConfig] = None):
        """
        Initialize serial communicator.

        Args:
            config: SerialConfig object. If None, uses defaults.
        """
        self.config = config or SerialConfig()
        self.serial_port: Optional[serial.Serial] = None

        self.tx_queue = queue.Queue()
        self.rx_thread: Optional[threading.Thread] = None
        self.running = False

        self.on_feedback: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None

        self.is_connected = False
        self.last_status = "IDLE"

    def connect(self, port: Optional[str] = None) -> bool:
        """
        Connect to ESP32 via serial port.

        Args:
            port: Serial port name (e.g., "COM3", "/dev/ttyUSB0")
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if port:
                self.config.port = port
            
            print(f"[Serial] Attempting to connect to {self.config.port}...")
            
            self.serial_port = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.write_timeout
            )
            
            # Small delay untuk stabilisasi
            time.sleep(0.5)
            
            self.is_connected = True
            print(f"[Serial] ✓ Connected to {self.config.port}")
            
            # Start RX thread
            self.running = True
            self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
            self.rx_thread.start()
            
            if self.on_connected:
                self.on_connected()
            
            return True
            
        except serial.SerialException as e:
            self.is_connected = False
            error_msg = f"Connection failed: {e}"
            print(f"[Serial] {error_msg}")
            if self.on_error:
                self.on_error(error_msg)
            return False
    
    def disconnect(self):
        """Disconnect from serial port."""
        if not self.is_connected:
            return
        
        print("[Serial] Disconnecting...")
        
        self.running = False
        if self.rx_thread:
            self.rx_thread.join(timeout=2.0)
        
        if self.serial_port:
            self.serial_port.close()
        
        self.is_connected = False
        print("[Serial] ✓ Disconnected")
        
        if self.on_disconnected:
            self.on_disconnected()
    
    def send_move_command(
        self,
        theta_deg: float,
        r_cm: float,
        h_cm: float,
        magnet_on: bool = False
    ) -> bool:
        """
        Queue MOVE command to ESP32.
        
        Args:
            theta_deg: Yaw angle (degrees)
            r_cm: Radial distance (cm)
            h_cm: Height (cm)
            magnet_on: Electromagnet state
        
        Returns:
            True if queued successfully
        """
        if not self.is_connected:
            if self.on_error:
                self.on_error("Not connected to ESP32")
            return False

        cmd = self._json_command(
            {
                "command": "MOVE",
                "theta": round(theta_deg, 1),
                "r": round(r_cm, 1),
                "h": round(h_cm, 1),
                "magnet": magnet_on,
            }
        )

        self.tx_queue.put(cmd)
        print(f"[Serial] Queued: {cmd.strip()}")
        return True
    
    def send_home_command(self) -> bool:
        """Send HOME command."""
        return self._queue_simple_command("HOME")

    def send_estop_command(self) -> bool:
        """Send EMERGENCY STOP command."""
        return self._queue_simple_command("ESTOP")

    def send_status_command(self) -> bool:
        """Send STATUS command."""
        return self._queue_simple_command("STATUS")

    def _queue_simple_command(self, command: str) -> bool:
        if not self.is_connected:
            if self.on_error:
                self.on_error("Not connected to ESP32")
            return False

        cmd = self._json_command({"command": command})
        self.tx_queue.put(cmd)
        print(f"[Serial] Queued: {cmd.strip()}")
        return True

    @staticmethod
    def _json_command(payload: Dict[str, Any]) -> str:
        """Serialize one command as compact newline-delimited JSON."""
        return json.dumps(payload, separators=(",", ":")) + "\n"

    def _rx_loop(self):
        """
        Receive loop - runs in separate thread.
        Continuously reads from serial port.
        """
        buffer = ""

        while self.running:
            try:
                if self.serial_port and self.serial_port.in_waiting:
                    # Read available data
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    buffer += data.decode("utf-8", errors="ignore")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line and self.config.use_feedback:
                            self._process_feedback(line)

                try:
                    cmd = self.tx_queue.get(timeout=0.1)
                    self._send_command(cmd)
                except queue.Empty:
                    pass

            except Exception as e:
                print(f"[Serial RX] Error: {e}")
                if self.on_error:
                    self.on_error(f"RX error: {e}")
                break
    
    def _send_command(self, cmd: str):
        """
        Send command ke ESP32.
        
        Args:
            cmd: JSON command string with newline.
        """
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.write(cmd.encode('utf-8'))
                self.serial_port.flush()
                print(f"[Serial TX] Sent: {cmd.strip()}")
        except Exception as e:
            print(f"[Serial TX] Error: {e}")
            if self.on_error:
                self.on_error(f"TX error: {e}")

    def _process_feedback(self, line: str):
        """
        Process JSON feedback dari ESP32.

        Expected examples:
        - {"status":"IDLE"}
        - {"status":"MOVING"}
        - {"status":"DONE"}
        - {"status":"ERROR","message":"Invalid command"}
        - {"type":"position","theta":90.0,"r":25.0,"h":0.0}

        Args:
            line: Received JSON line.
        """
        print(f"[Serial RX] Received: {line}")

        try:
            feedback = json.loads(line)
        except json.JSONDecodeError as e:
            self.last_status = "ERROR"
            error_msg = f"Invalid JSON feedback: {e.msg}"
            print(f"[Serial] {error_msg}")
            if self.on_error:
                self.on_error(error_msg)
            return

        status = feedback.get("status")
        if status:
            self.last_status = str(status).upper()

        if feedback.get("type") == "position":
            try:
                theta = float(feedback["theta"])
                r = float(feedback["r"])
                h = float(feedback["h"])
                print(f"[Serial] Current position: theta={theta} deg, r={r}cm, h={h}cm")
            except (KeyError, TypeError, ValueError):
                if self.on_error:
                    self.on_error(f"Invalid position feedback: {line}")

        # Keep callback signature as str; callers receive the raw JSON line.
        if self.on_feedback:
            self.on_feedback(line)
    
    @staticmethod
    def list_available_ports():
        """
        List all available serial ports.
        
        Returns:
            List of (port_name, description) tuples
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append((port.device, port.description))
        return ports
    
    def set_callbacks(
        self,
        on_feedback: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_connected: Optional[Callable] = None,
        on_disconnected: Optional[Callable] = None
    ):
        """Set callback functions."""
        if on_feedback:
            self.on_feedback = on_feedback
        if on_error:
            self.on_error = on_error
        if on_connected:
            self.on_connected = on_connected
        if on_disconnected:
            self.on_disconnected = on_disconnected


# === Utility: Auto-detect ESP32 port ===

def auto_detect_esp32_port() -> Optional[str]:
    """
    Auto-detect ESP32 port berdasarkan VID/PID.
    
    ESP32 biasanya pakai CH340 atau CP2102 serial chip.
    
    Returns:
        Port name jika ditemukan, None otherwise
    """
    for port in serial.tools.list_ports.comports():
        # CH340 (common ESP32 board)
        if port.vid == 0x1A86 and port.pid == 0x7523:
            return port.device
        # CP2102 (another common option)
        if port.vid == 0x10C4 and port.pid == 0xEA60:
            return port.device
    
    return None
