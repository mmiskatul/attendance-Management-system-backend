"""Face enrollment endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.v1.serializers import to_face_embedding_response, to_student_response
from app.db.dependencies import get_enrollment_service, require_roles
from app.models.common import UserRole
from app.models.user import UserDocument
from app.schemas.face import FaceEnrollmentRequest, FaceEnrollmentResponse, RejectedSampleResponse
from app.services.enrollment import EnrollmentService


router = APIRouter(prefix="/faces", tags=["faces"])


@router.post("/enroll", response_model=FaceEnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_faces(
    payload: FaceEnrollmentRequest,
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
    current_user: UserDocument = Depends(require_roles(UserRole.ADMIN)),
) -> FaceEnrollmentResponse:
    result = await enrollment_service.enroll(
        student_id=payload.student_id,
        image_samples=[(sample.image_base64, sample.pose) for sample in payload.samples],
        actor_id=current_user.id or current_user.username,
        tenant_id=payload.tenant_id or current_user.tenant_id,
        campus_id=payload.campus_id,
    )
    return FaceEnrollmentResponse(
        student=to_student_response(result.student),
        enrolled_count=len(result.enrolled_embeddings),
        embeddings=[to_face_embedding_response(item) for item in result.enrolled_embeddings],
        rejected_samples=[RejectedSampleResponse(index=item.index, reason=item.reason) for item in result.rejected_samples],
    )
