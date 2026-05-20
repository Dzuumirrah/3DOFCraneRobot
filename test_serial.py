"""
Serial Communication Test Utility
Robot Crane 3-DOF

Test serial commands without running full GUI.
Useful untuk debugging, rapid prototyping, ESP32 firmware development.
"""

import serial
import serial.tools.list_ports
import time
import sys
import params
from serial_comm import CraneSerialComm, SerialConfig, auto_detect_esp32_port


def list_ports():
    """List available serial ports."""
    print("\n=== Available Serial Ports ===")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("No serial ports found!")
        return []
    
    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device:15} | {port.description}")
    
    return [p.device for p in ports]


def test_connection(port: str):
    """Test basic serial connection."""
    print(f"\n=== Testing Connection: {port} ===")
    
    config = SerialConfig(port=port, baudrate=params.SERIAL_BAUD_RATE)
    comm = CraneSerialComm(config)
    
    # Setup callbacks
    comm.set_callbacks(
        on_feedback=lambda x: print(f"[RX] {x}"),
        on_error=lambda x: print(f"[Error] {x}"),
        on_connected=lambda: print("[Connected]"),
        on_disconnected=lambda: print("[Disconnected]")
    )
    
    # Try connect
    if not comm.connect():
        print("Connection failed!")
        return False
    
    time.sleep(0.5)
    
    # Send STATUS command
    print("\nSending STATUS command...")
    comm.send_status_command()
    time.sleep(1)
    
    # Send HOME command
    print("Sending HOME command...")
    comm.send_home_command()
    time.sleep(1)
    
    comm.disconnect()
    return True


def test_move_command(port: str, theta: float, r: float, h: float):
    """Test MOVE command."""
    print(f"\n=== Testing MOVE Command ===")
    print(f"Target: θ={theta}°, r={r}cm, h={h}cm")
    
    config = SerialConfig(port=port, baudrate=params.SERIAL_BAUD_RATE)
    comm = CraneSerialComm(config)
    
    comm.set_callbacks(
        on_feedback=lambda x: print(f"[RX] {x}"),
        on_error=lambda x: print(f"[Error] {x}")
    )
    
    if not comm.connect():
        return False
    
    time.sleep(0.5)
    print("Sending MOVE command...")
    comm.send_move_command(theta, r, h, magnet_on=True)
    
    # Wait for completion
    time.sleep(5)
    comm.disconnect()
    return True


def interactive_mode(port: str):
    """Interactive serial testing mode."""
    print(f"\n=== Interactive Mode: {port} ===")
    print("Commands:")
    print("  MOVE theta r h magnet   - Send move command")
    print("  HOME                    - Send home command")
    print("  ESTOP                   - Emergency stop")
    print("  STATUS                  - Get status")
    print("  QUIT                    - Exit")
    
    config = SerialConfig(port=port, baudrate=params.SERIAL_BAUD_RATE)
    comm = CraneSerialComm(config)
    
    comm.set_callbacks(
        on_feedback=lambda x: print(f"\n[Feedback] {x}\n> ", end=""),
        on_error=lambda x: print(f"\n[Error] {x}\n> ", end="")
    )
    
    if not comm.connect():
        print("Connection failed!")
        return
    
    print(f"\nConnected to {port}")
    print("Type command (or 'help' for options):\n")
    
    try:
        while True:
            try:
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == "quit":
                    break
                
                elif user_input.lower() == "help":
                    print("\nCommands:")
                    print("  MOVE theta r h magnet   - theta: 0-180°, r: 0-45cm, h: 0-50cm, magnet: 0 or 1")
                    print("  HOME                    - Move to home (90°, 25cm, 0cm)")
                    print("  ESTOP                   - Emergency stop")
                    print("  STATUS                  - Request position feedback")
                    print("  QUIT                    - Exit\n")
                
                elif user_input.upper().startswith("MOVE"):
                    parts = user_input.split()
                    if len(parts) >= 5:
                        theta = float(parts[1])
                        r = float(parts[2])
                        h = float(parts[3])
                        magnet = bool(int(parts[4]))
                        comm.send_move_command(theta, r, h, magnet)
                        print(f'→ Sent: {{"command":"MOVE","theta":{theta},"r":{r},"h":{h},"magnet":{str(magnet).lower()}}}')
                    else:
                        print("Usage: MOVE theta r h magnet")
                
                elif user_input.upper() == "HOME":
                    comm.send_home_command()
                    print("→ Sent: HOME")
                
                elif user_input.upper() == "ESTOP":
                    comm.send_estop_command()
                    print("→ Sent: ESTOP")
                
                elif user_input.upper() == "STATUS":
                    comm.send_status_command()
                    print("→ Sent: STATUS")
                
                else:
                    print(f"Unknown command: {user_input}")
                
                time.sleep(0.5)
            
            except ValueError as e:
                print(f"Invalid input: {e}")
            except KeyboardInterrupt:
                print("\n")
                break
    
    finally:
        comm.disconnect()
        print("Disconnected")


def main():
    """Main entry point."""
    print("""
╔════════════════════════════════════════════════════════════════╗
║     Robot Crane 3-DOF Serial Communication Test Utility       ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    # Try auto-detect first
    print("Attempting to auto-detect ESP32...")
    auto_port = auto_detect_esp32_port()
    if auto_port:
        print(f"✓ Found ESP32 at {auto_port}")
        use_auto = input("Use this port? (y/n): ").lower() == 'y'
        if use_auto:
            port = auto_port
        else:
            ports = list_ports()
            if not ports:
                return
            choice = int(input("Select port (number): ")) - 1
            if 0 <= choice < len(ports):
                port = ports[choice]
            else:
                print("Invalid choice")
                return
    else:
        print("Auto-detect failed, listing available ports...")
        ports = list_ports()
        if not ports:
            return
        choice = int(input("Select port (number): ")) - 1
        if 0 <= choice < len(ports):
            port = ports[choice]
        else:
            print("Invalid choice")
            return
    
    # Test menu
    while True:
        print("\n=== Test Menu ===")
        print("1. Test connection")
        print("2. Test MOVE command")
        print("3. Interactive mode")
        print("4. Exit")
        
        choice = input("Select (1-4): ").strip()
        
        if choice == "1":
            test_connection(port)
        
        elif choice == "2":
            try:
                theta = float(input("Theta (0-180): "))
                r = float(input("Radius (0-45): "))
                h = float(input("Height (0-50): "))
                test_move_command(port, theta, r, h)
            except ValueError:
                print("Invalid input")
        
        elif choice == "3":
            interactive_mode(port)
        
        elif choice == "4":
            break
        
        else:
            print("Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
