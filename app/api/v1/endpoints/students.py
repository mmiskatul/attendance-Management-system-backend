"""Student endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.v1.serializers import to_student_response
from app.db.dependencies import get_student_service, require_roles
from app.models.common import UserRole
from app.models.user import UserDocument
from app.schemas.student import StudentRegisterRequest, StudentResponse
from app.services.student import StudentService


router = APIRouter(prefix="/students", tags=["students"])


@router.post("/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def register_student(
    payload: StudentRegisterRequest,
    student_service: StudentService = Depends(get_student_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN)),
) -> StudentResponse:
    student = await student_service.register_student(
        full_name=payload.full_name,
        department=payload.department,
        batch=payload.batch,
        semester=payload.semester,
        email=payload.email,
        phone=payload.phone,
        barcode_value=payload.barcode_value,
        actor_id=current_user.id or current_user.username,
        tenant_id=payload.tenant_id or current_user.tenant_id,
        campus_id=payload.campus_id,
    )
    return to_student_response(student)


@router.get("/{student_id}", response_model=StudentResponse, status_code=status.HTTP_200_OK)
async def get_student(
    student_id: str,
    student_service: StudentService = Depends(get_student_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> StudentResponse:
    student = await student_service.get_student(current_user.tenant_id, student_id)
    return to_student_response(student)
