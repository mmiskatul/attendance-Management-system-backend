"""Face enrollment endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.v1.serializers import to_face_embedding_response, to_student_response
from app.db.dependencies import get_enrollment_service, require_roles
from app.models.common import UserRole
from app.models.user import UserDocument
from app.schemas.face import (
    FaceAnalyzeRequest,
    FaceAnalyzeResponse,
    FaceEnrollmentRequest,
    FaceEnrollmentResponse,
    RejectedSampleResponse,
)
from app.services.enrollment import EnrollmentService


router = APIRouter(prefix="/faces", tags=["faces"])


@router.post("/analyze", response_model=FaceAnalyzeResponse, status_code=status.HTTP_200_OK)
async def analyze_face(
    payload: FaceAnalyzeRequest,
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
    _: UserDocument = Depends(require_roles(UserRole.ADMIN)),
) -> FaceAnalyzeResponse:
    result = await enrollment_service.analyze(
        image_payload=payload.image_base64,
        expected_pose=payload.expected_pose,
    )
    return FaceAnalyzeResponse(
        provider_name=result.provider_name,
        pose_reliable=result.pose_reliable,
        faces_count=result.faces_count,
        primary_pose=result.primary_pose,
        detection_score=result.detection_score,
        quality_score=result.quality_score,
        expected_pose=result.expected_pose,
        pose_match=result.pose_match,
    )


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
