"""Domain enums and shared models."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"


class StudentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    GRADUATED = "graduated"


class AttendanceStatus(str, Enum):
    MARKED = "marked"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


class AttendanceSession(str, Enum):
    DAILY = "daily"


class AuditAction(str, Enum):
    LOGIN = "auth.login"
    STUDENT_REGISTERED = "student.registered"
    FACE_ENROLLED = "face.enrolled"
    ATTENDANCE_MARKED = "attendance.marked"
    ATTENDANCE_DUPLICATE = "attendance.duplicate"
    ATTENDANCE_REJECTED = "attendance.rejected"
    AUDIT_VIEWED = "audit.viewed"
