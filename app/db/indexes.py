"""MongoDB collection indexes."""

from pymongo import ASCENDING, DESCENDING, IndexModel


def student_indexes() -> list[IndexModel]:
    return [
        IndexModel([("tenant_id", ASCENDING), ("student_id", ASCENDING)], unique=True, name="uq_student_id"),
        IndexModel([("tenant_id", ASCENDING), ("barcode_value", ASCENDING)], unique=True, name="uq_barcode_value"),
        IndexModel(
            [("tenant_id", ASCENDING), ("campus_id", ASCENDING), ("department", ASCENDING), ("status", ASCENDING)],
            name="ix_students_filters",
        ),
    ]


def face_embedding_indexes() -> list[IndexModel]:
    return [
        IndexModel(
            [("tenant_id", ASCENDING), ("campus_id", ASCENDING), ("student_id", ASCENDING), ("is_active", ASCENDING)],
            name="ix_embeddings_student_active",
        ),
        IndexModel([("tenant_id", ASCENDING), ("campus_id", ASCENDING), ("created_at", DESCENDING)], name="ix_embeddings_created_at"),
    ]


def attendance_indexes() -> list[IndexModel]:
    return [
        IndexModel(
            [
                ("tenant_id", ASCENDING),
                ("student_id", ASCENDING),
                ("attendance_date", ASCENDING),
                ("attendance_session", ASCENDING),
            ],
            unique=True,
            name="uq_attendance_daily_session",
        ),
        IndexModel([("tenant_id", ASCENDING), ("campus_id", ASCENDING), ("attendance_date", DESCENDING)], name="ix_attendance_daily"),
        IndexModel([("device_id", ASCENDING), ("created_at", DESCENDING)], name="ix_attendance_device"),
    ]


def user_indexes() -> list[IndexModel]:
    return [
        IndexModel([("tenant_id", ASCENDING), ("username", ASCENDING)], unique=True, name="uq_username"),
        IndexModel([("tenant_id", ASCENDING), ("role", ASCENDING), ("is_active", ASCENDING)], name="ix_user_role"),
    ]


def audit_indexes() -> list[IndexModel]:
    return [
        IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="ix_audit_created"),
        IndexModel([("actor_id", ASCENDING), ("created_at", DESCENDING)], name="ix_audit_actor"),
        IndexModel([("target_type", ASCENDING), ("target_id", ASCENDING)], name="ix_audit_target"),
    ]
