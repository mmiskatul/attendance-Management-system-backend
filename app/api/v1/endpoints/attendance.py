"""Attendance endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.api.v1.serializers import to_attendance_record_response, to_student_response
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, AuthenticationAppError, AuthorizationAppError, RateLimitAppError
from app.core.security import decode_access_token
from app.db.dependencies import build_rate_limit_dependency, get_attendance_service, get_runtime_settings, require_roles
from app.models.common import AttendanceStatus, UserRole
from app.models.user import UserDocument
from app.schemas.attendance import (
    AttendanceRecognizeRequest,
    AttendanceRecognizeResponse,
    AttendanceStreamConfigureMessage,
    AttendanceStreamEvent,
    AttendanceStreamFrameMessage,
    DailyAttendanceResponse,
    StudentAttendanceResponse,
)
from app.services.attendance import AttendanceService
from app.utils.time import current_local_date


settings_snapshot = get_settings()
attendance_rate_limit = build_rate_limit_dependency(
    namespace="attendance",
    limit=settings_snapshot.attendance_rate_limit_per_minute,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _build_stream_event(
    *,
    event: str,
    message: str,
    device_id: str | None = None,
    campus_id: str | None = None,
    recognized: bool | None = None,
    confidence_score: float | None = None,
    attendance_status: AttendanceStatus | None = None,
    matched_embedding_id: str | None = None,
    student=None,
    attendance_record=None,
    cooldown_seconds: int | None = None,
) -> dict[str, object]:
    return AttendanceStreamEvent(
        event=event,
        message=message,
        device_id=device_id,
        campus_id=campus_id,
        recognized=recognized,
        confidence_score=confidence_score,
        attendance_status=attendance_status,
        matched_embedding_id=matched_embedding_id,
        student=to_student_response(student) if student else None,
        attendance_record=to_attendance_record_response(attendance_record) if attendance_record else None,
        cooldown_seconds=cooldown_seconds,
    ).model_dump(mode="json", by_alias=True)


async def _authenticate_websocket(websocket: WebSocket) -> tuple[AttendanceService, Settings, UserDocument]:
    settings: Settings = getattr(websocket.app.state, "settings", get_settings())
    container = getattr(websocket.app.state, "container", None)
    if container is None:
        raise RuntimeError("Application container is not initialized.")

    token = websocket.query_params.get("token")
    if not token:
        raise AuthenticationAppError("Missing bearer token.")

    payload = decode_access_token(
        token,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    user = await container.auth_service.get_active_user(payload.sub)
    if user.role not in {UserRole.ADMIN, UserRole.OPERATOR}:
        raise AuthorizationAppError()
    return container.attendance_service, settings, user


@router.websocket("/ws/recognize")
async def recognize_attendance_stream(websocket: WebSocket) -> None:
    try:
        attendance_service, settings, current_user = await _authenticate_websocket(websocket)
    except AuthenticationAppError as exc:
        await websocket.close(code=4401, reason=exc.detail[:120])
        return
    except AuthorizationAppError as exc:
        await websocket.close(code=4403, reason=exc.detail[:120])
        return

    container = getattr(websocket.app.state, "container", None)
    await websocket.accept()
    await websocket.send_json(
        _build_stream_event(
            event="ready",
            message="WebSocket connected. Send stream configuration before frames.",
        )
    )

    stream_config: AttendanceStreamConfigureMessage | None = None
    client_ip = websocket.headers.get("x-forwarded-for") or (websocket.client.host if websocket.client else "unknown")

    try:
        while True:
            try:
                incoming = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                await websocket.send_json(
                    _build_stream_event(
                        event="error",
                        message="Invalid WebSocket payload. JSON object expected.",
                    )
                )
                continue

            if not isinstance(incoming, dict):
                await websocket.send_json(
                    _build_stream_event(
                        event="error",
                        message="Invalid WebSocket payload. JSON object expected.",
                    )
                )
                continue

            message_type = incoming.get("type")

            try:
                if message_type == "configure":
                    stream_config = AttendanceStreamConfigureMessage.model_validate(incoming)
                    await websocket.send_json(
                        _build_stream_event(
                            event="configured",
                            message="Live recognition stream configured.",
                            device_id=stream_config.device_id,
                            campus_id=stream_config.campus_id or settings.default_campus_id,
                        )
                    )
                    continue

                if message_type == "ping":
                    await websocket.send_json(
                        _build_stream_event(
                            event="pong",
                            message="Stream alive.",
                            device_id=stream_config.device_id if stream_config else None,
                            campus_id=(stream_config.campus_id if stream_config else None) or settings.default_campus_id,
                        )
                    )
                    continue

                if message_type == "stop":
                    await websocket.send_json(
                        _build_stream_event(
                            event="stopped",
                            message="Live recognition stream stopped by client.",
                            device_id=stream_config.device_id if stream_config else None,
                            campus_id=(stream_config.campus_id if stream_config else None) or settings.default_campus_id,
                        )
                    )
                    await websocket.close(code=1000)
                    break

                if message_type != "frame":
                    await websocket.send_json(
                        _build_stream_event(
                            event="error",
                            message="Unsupported WebSocket message type.",
                        )
                    )
                    continue

                if stream_config is None:
                    await websocket.send_json(
                        _build_stream_event(
                            event="error",
                            message="Stream is not configured. Send a configure message first.",
                        )
                    )
                    continue

                frame = AttendanceStreamFrameMessage.model_validate(incoming)
                await container.rate_limiter.enforce(
                    key=f"attendance-ws:{current_user.id or current_user.username}:{client_ip}:{stream_config.device_id}",
                    limit=settings.attendance_rate_limit_per_minute,
                    window_seconds=60,
                )
                resolved_campus_id = stream_config.campus_id or settings.default_campus_id
                await websocket.send_json(
                    _build_stream_event(
                        event="processing",
                        message="Analyzing live frame.",
                        device_id=stream_config.device_id,
                        campus_id=resolved_campus_id,
                    )
                )

                result = await attendance_service.recognize(
                    image_payload=frame.image_base64,
                    device_id=stream_config.device_id,
                    actor_id=current_user.id or current_user.username,
                    tenant_id=current_user.tenant_id,
                    campus_id=stream_config.campus_id,
                    attendance_session=stream_config.attendance_session,
                    captured_at=frame.captured_at,
                )

                event_name = {
                    AttendanceStatus.MARKED: "recognized",
                    AttendanceStatus.DUPLICATE: "duplicate",
                    AttendanceStatus.UNKNOWN: "unknown",
                    AttendanceStatus.REJECTED: "rejected",
                }.get(result.status, "result")
                cooldown_seconds = 5 if result.status == AttendanceStatus.MARKED else 3 if result.status == AttendanceStatus.DUPLICATE else None

                await websocket.send_json(
                    _build_stream_event(
                        event=event_name,
                        message=result.message,
                        device_id=stream_config.device_id,
                        campus_id=resolved_campus_id,
                        recognized=result.recognized,
                        confidence_score=result.confidence_score,
                        attendance_status=result.status,
                        matched_embedding_id=result.matched_embedding_id,
                        student=result.student,
                        attendance_record=result.attendance_record,
                        cooldown_seconds=cooldown_seconds,
                    )
                )
            except ValidationError as exc:
                await websocket.send_json(
                    _build_stream_event(
                        event="error",
                        message="WebSocket message validation failed.",
                    )
                    | {"details": exc.errors()}
                )
            except RateLimitAppError as exc:
                await websocket.send_json(
                    _build_stream_event(
                        event="rate_limited",
                        message=exc.detail,
                        device_id=stream_config.device_id if stream_config else None,
                        campus_id=(stream_config.campus_id if stream_config else None) or settings.default_campus_id,
                    )
                )
            except AppError as exc:
                await websocket.send_json(
                    _build_stream_event(
                        event="error",
                        message=exc.detail,
                        device_id=stream_config.device_id if stream_config else None,
                        campus_id=(stream_config.campus_id if stream_config else None) or settings.default_campus_id,
                    )
                )
    except WebSocketDisconnect:
        return


@router.post("/recognize", response_model=AttendanceRecognizeResponse, status_code=status.HTTP_200_OK)
async def recognize_attendance(
    payload: AttendanceRecognizeRequest,
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
    _: None = Depends(attendance_rate_limit),
) -> AttendanceRecognizeResponse:
    result = await attendance_service.recognize(
        image_payload=payload.image_base64,
        device_id=payload.device_id,
        actor_id=current_user.id or current_user.username,
        tenant_id=payload.tenant_id or current_user.tenant_id,
        campus_id=payload.campus_id,
        attendance_session=payload.attendance_session,
        captured_at=payload.captured_at,
    )
    return AttendanceRecognizeResponse(
        recognized=result.recognized,
        student=to_student_response(result.student) if result.student else None,
        confidence_score=result.confidence_score,
        attendance_status=result.status,
        matched_embedding_id=result.matched_embedding_id,
        attendance_record=to_attendance_record_response(result.attendance_record) if result.attendance_record else None,
        message=result.message,
    )


@router.get("/student/{student_id}", response_model=StudentAttendanceResponse, status_code=status.HTTP_200_OK)
async def get_student_attendance(
    student_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> StudentAttendanceResponse:
    records = await attendance_service.list_student_attendance(
        tenant_id=current_user.tenant_id,
        student_id=student_id,
        skip=skip,
        limit=limit,
    )
    return StudentAttendanceResponse(
        student_id=student_id,
        records=[to_attendance_record_response(item) for item in records],
    )


@router.get("/daily", response_model=DailyAttendanceResponse, status_code=status.HTTP_200_OK)
async def get_daily_attendance(
    attendance_date: date | None = Query(default=None),
    campus_id: str | None = Query(default=None),
    attendance_service: AttendanceService = Depends(get_attendance_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
    settings: Settings = Depends(get_runtime_settings),
) -> DailyAttendanceResponse:
    resolved_date = attendance_date or current_local_date(settings.timezone)
    records = await attendance_service.list_daily_attendance(
        tenant_id=current_user.tenant_id,
        attendance_date=resolved_date,
        campus_id=campus_id,
    )
    return DailyAttendanceResponse(
        attendance_date=resolved_date,
        campus_id=campus_id,
        total_records=len(records),
        records=[to_attendance_record_response(item) for item in records],
    )
