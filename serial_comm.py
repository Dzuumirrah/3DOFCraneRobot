"""
Serial Communication Module
Robot Crane 3-DOF

Handles communication to ESP32 microcontroller via USB Serial.
Protocol: Simple text-based commands
"""

import serial
import serial.tools.list_ports
import threading
import queue
import time
from typing import Optional, Callable
from dataclasses import dataclass

@dataclass
class SerialConfig:
    """Serial port configuration."""
    port: str = "COM7"              # Default Windows port
    baudrate: int = 115200          # Baud rate
    timeout: float = 1.0            # Read timeout
    write_timeout: float = 1.0      # Write timeout


class CraneSerialComm:
    """
    Serial communication handler untuk Robot Crane.
    
    Features:
    - Non-blocking TX/RX dengan threading
    - Command queue management
    - Feedback parsing
    - Connection state tracking
    """
    
    # Command format constants
    COMMAND_TEMPLATE = "MOVE,{theta:.1f},{r:.1f},{h:.1f},{magnet}\n"
    HOME_COMMAND = "HOME\n"
    ESTOP_COMMAND = "ESTOP\n"
    STATUS_COMMAND = "STATUS\n"
    
    def __init__(self, config: Optional[SerialConfig] = None):
        """
        Initialize serial communicator.
        
        Args:
            config: SerialConfig object. If None, uses defaults.
        """
        self.config = config or SerialConfig()
        self.serial_port: Optional[serial.Serial] = None
        
        # Threading
        self.tx_queue = queue.Queue()      # Command queue
        self.rx_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Callbacks
        self.on_feedback: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
        
        # State
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
            error_msg = f"Connection failed: {str(e)}"
            print(f"[Serial] ✗ {error_msg}")
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
        
        magnet_state = "1" if magnet_on else "0"
        cmd = self.COMMAND_TEMPLATE.format(
            theta=theta_deg,
            r=r_cm,
            h=h_cm,
            magnet=magnet_state
        )
        
        self.tx_queue.put(cmd)
        print(f"[Serial] Queued: {cmd.strip()}")
        return True
    
    def send_home_command(self) -> bool:
        """Send HOME command."""
        if not self.is_connected:
            return False
        
        self.tx_queue.put(self.HOME_COMMAND)
        print("[Serial] Queued: HOME")
        return True
    
    def send_estop_command(self) -> bool:
        """Send EMERGENCY STOP command."""
        if not self.is_connected:
            return False
        
        self.tx_queue.put(self.ESTOP_COMMAND)
        print("[Serial] Queued: ESTOP")
        return True
    
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
                    buffer += data.decode('utf-8', errors='ignore')
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._process_feedback(line)
                
                # Check TX queue
                try:
                    cmd = self.tx_queue.get(timeout=0.1)
                    self._send_command(cmd)
                except queue.Empty:
                    pass
                
            except Exception as e:
                print(f"[Serial RX] Error: {str(e)}")
                if self.on_error:
                    self.on_error(f"RX error: {str(e)}")
                break
    
    def _send_command(self, cmd: str):
        """
        Send command ke ESP32.
        
        Args:
            cmd: Command string (with newline)
        """
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.write(cmd.encode('utf-8'))
                self.serial_port.flush()
                print(f"[Serial TX] Sent: {cmd.strip()}")
        except Exception as e:
            print(f"[Serial TX] Error: {str(e)}")
            if self.on_error:
                self.on_error(f"TX error: {str(e)}")
    
    def _process_feedback(self, line: str):
        """
        Process feedback dari ESP32.
        
        Expected formats:
        - "IDLE"
        - "MOVING"
        - "DONE"
        - "ERROR: <message>"
        - "POS,theta,r,h" (position feedback)
        
        Args:
            line: Received line
        """
        print(f"[Serial RX] Received: {line}")
        
        # Parse feedback
        if line == "IDLE":
            self.last_status = "IDLE"
        elif line == "MOVING":
            self.last_status = "MOVING"
        elif line == "DONE":
            self.last_status = "DONE"
        elif line.startswith("ERROR"):
            self.last_status = "ERROR"
        elif line.startswith("POS"):
            # Position feedback: POS,theta,r,h
            try:
                parts = line.split(',')
                if len(parts) >= 4:
                    theta = float(parts[1])
                    r = float(parts[2])
                    h = float(parts[3])
                    print(f"[Serial] Current position: θ={theta}°, r={r}cm, h={h}cm")
            except ValueError:
                pass
        
        # Emit callback
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