"""
Inverse Kinematics & Constraint Module
Robot Crane 3-DOF

Math:
  θ = atan2(y, x)       # Yaw angle (Joint 1)
  r = sqrt(x² + y²)     # Radial distance (Joint 2)
  h = target_height     # Hoist height (Joint 3)
"""

import math
from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class JointLimits:
    """Physical limits for each joint."""
    theta_min: float = -180.0      # degrees
    theta_max: float = 180.0       # degrees
    r_min: float = 0.0              # cm (at base)
    r_max: float = 45.0             # cm (max reach)
    h_min: float = 0.0              # cm (lowest point)
    h_max: float = 50.0             # cm (highest point)

@dataclass
class JointAngles:
    """Joint configuration result."""
    theta_deg: float                # Yaw angle (degrees)
    r_cm: float                     # Radial distance (cm)
    h_cm: float                     # Height (cm)
    is_valid: bool = True           # Reached valid state?
    error_msg: str = ""             # Error detail jika invalid


class CraneKinematics:
    """
    3-DOF Crane Inverse Kinematics Solver
    """
    
    def __init__(self, limits: Optional[JointLimits] = None):
        """
        Initialize kinematics solver.
        
        Args:
            limits: JointLimits object. If None, uses defaults.
        """
        self.limits = limits or JointLimits()
        
        # Workspace parameters (cm)
        self.workspace_x_min = -self.limits.r_max
        self.workspace_x_max = self.limits.r_max
        self.workspace_y_min = -self.limits.r_max
        self.workspace_y_max = self.limits.r_max
    
    def calculate(
        self,
        x_cm: float,
        y_cm: float,
        h_cm: float,
        validate: bool = True
    ) -> JointAngles:
        """
        Calculate inverse kinematics for target position.
        
        Args:
            x_cm: Target X coordinate (cm)
            y_cm: Target Y coordinate (cm)
            h_cm: Target height (cm)
            validate: Whether to validate and clamp values
        
        Returns:
            JointAngles with calculated values
        """
        try:
            # === Step 1: Calculate raw kinematics ===
            theta_deg = self._calculate_theta(x_cm, y_cm)
            r_cm = self._calculate_radial_distance(x_cm, y_cm)
            
            result = JointAngles(
                theta_deg=theta_deg,
                r_cm=r_cm,
                h_cm=h_cm,
                is_valid=True,
                error_msg=""
            )
            
            # === Step 2: Validate and constrain ===
            if validate:
                result = self._apply_constraints(result)
            
            return result
            
        except Exception as e:
            return JointAngles(
                theta_deg=0,
                r_cm=0,
                h_cm=0,
                is_valid=False,
                error_msg=f"IK calculation failed: {str(e)}"
            )
    
    def _calculate_theta(self, x_cm: float, y_cm: float) -> float:
        """
        Calculate yaw angle (theta) from Cartesian coordinates.
        
        θ = atan2(y, x)
        
        Args:
            x_cm: X coordinate
            y_cm: Y coordinate
        
        Returns:
            Theta in degrees [-180, 180]
        """
        # Use atan2 for proper quadrant handling
        theta_rad = math.atan2(y_cm, x_cm)
        theta_deg = math.degrees(theta_rad)
        
        return theta_deg
    
    def _calculate_radial_distance(self, x_cm: float, y_cm: float) -> float:
        """
        Calculate radial distance (r) from Cartesian coordinates.
        
        r = sqrt(x² + y²)
        
        Args:
            x_cm: X coordinate
            y_cm: Y coordinate
        
        Returns:
            Distance in cm
        """
        r_cm = math.sqrt(x_cm**2 + y_cm**2)
        return r_cm
    
    def _apply_constraints(self, joints: JointAngles) -> JointAngles:
        """
        Apply joint limits and workspace constraints.
        
        Args:
            joints: Raw joint angles
        
        Returns:
            Constrained joint angles with validation status
        """
        errors = []
        
        # === Theta constraints ===
        if joints.theta_deg < self.limits.theta_min or \
           joints.theta_deg > self.limits.theta_max:
            # Wrap angle to [-180, 180]
            theta_wrapped = self._wrap_angle(joints.theta_deg)
            
            if theta_wrapped < self.limits.theta_min or \
               theta_wrapped > self.limits.theta_max:
                errors.append(
                    f"θ={joints.theta_deg:.1f}° exceeds limit [{self.limits.theta_min}, {self.limits.theta_max}]"
                )
            else:
                joints.theta_deg = theta_wrapped
        
        # === Radial distance constraints ===
        if joints.r_cm < self.limits.r_min:
            errors.append(f"r={joints.r_cm:.1f}cm below minimum {self.limits.r_min}cm")
            joints.r_cm = self.limits.r_min
        
        if joints.r_cm > self.limits.r_max:
            errors.append(f"r={joints.r_cm:.1f}cm exceeds maximum {self.limits.r_max}cm")
            joints.r_cm = self.limits.r_max
        
        # === Height constraints ===
        if joints.h_cm < self.limits.h_min:
            errors.append(f"h={joints.h_cm:.1f}cm below minimum {self.limits.h_min}cm")
            joints.h_cm = self.limits.h_min
        
        if joints.h_cm > self.limits.h_max:
            errors.append(f"h={joints.h_cm:.1f}cm exceeds maximum {self.limits.h_max}cm")
            joints.h_cm = self.limits.h_max
        
        # === Update status ===
        if errors:
            joints.is_valid = False
            joints.error_msg = "; ".join(errors)
        
        return joints
    
    def is_reachable(self, x_cm: float, y_cm: float) -> bool:
        """
        Check if target position is within reachable workspace.
        
        Args:
            x_cm: Target X
            y_cm: Target Y
        
        Returns:
            True if reachable, False otherwise
        """
        r_cm = self._calculate_radial_distance(x_cm, y_cm)
        return self.limits.r_min <= r_cm <= self.limits.r_max
    
    def get_workspace_circle(self) -> Tuple[float, float, float]:
        """
        Get workspace circle parameters (center, radius).
        
        Useful untuk visualisasi di GUI.
        
        Returns:
            (center_x, center_y, radius) in cm
        """
        return (0.0, 0.0, self.limits.r_max)
    
    @staticmethod
    def _wrap_angle(angle_deg: float) -> float:
        """
        Wrap angle to [-180, 180] range.
        
        Args:
            angle_deg: Angle in degrees
        
        Returns:
            Wrapped angle in [-180, 180]
        """
        while angle_deg > 180:
            angle_deg -= 360
        while angle_deg < -180:
            angle_deg += 360
        return angle_deg
    
    def set_limits(self, **kwargs):
        """
        Update joint limits dynamically.
        
        Example:
            ik.set_limits(r_max=50, h_max=60)
        """
        for key, value in kwargs.items():
            if hasattr(self.limits, key):
                setattr(self.limits, key, value)


# === Utility Functions ===

def cartesian_to_polar(x_cm: float, y_cm: float) -> Tuple[float, float]:
    """Convert Cartesian (x,y) to Polar (r, θ)."""
    r = math.sqrt(x_cm**2 + y_cm**2)
    theta = math.degrees(math.atan2(y_cm, x_cm))
    return r, theta

def polar_to_cartesian(r_cm: float, theta_deg: float) -> Tuple[float, float]:
    """Convert Polar (r, θ) back to Cartesian (x, y)."""
    theta_rad = math.radians(theta_deg)
    x = r_cm * math.cos(theta_rad)
    y = r_cm * math.sin(theta_rad)
    return x, y