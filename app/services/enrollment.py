"""Face enrollment service."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import ConflictAppError, NotFoundAppError, ValidationAppError
from app.models.common import AuditAction
from app.models.face_embedding import FaceEmbeddingDocument
from app.models.student import StudentDocument
from app.repositories.face_embedding_repository import FaceEmbeddingRepository
from app.repositories.student_repository import StudentRepository
from app.services.audit import AuditService
from app.services.embedding_cache import EmbeddingCache
from app.services.face_engine.base import FaceEngine
from app.services.face_matcher import FaceMatcher, GalleryEmbedding
from app.services.image_quality import ImageQualityService
from app.services.liveness import LivenessDetector
from app.utils.embeddings import binary_to_embedding, embedding_to_binary
from app.utils.images import crop_image, decode_base64_image, ensure_minimum_size
from app.utils.time import utc_now


@dataclass(slots=True)
class SampleRejection:
    index: int
    reason: str


@dataclass(slots=True)
class EnrollmentResult:
    student: StudentDocument
    enrolled_embeddings: list[FaceEmbeddingDocument]
    rejected_samples: list[SampleRejection]


@dataclass(slots=True)
class FaceAnalysisResult:
    provider_name: str
    pose_reliable: bool
    faces_count: int
    primary_pose: str | None
    detection_score: float | None
    quality_score: float | None
    expected_pose: str | None
    pose_match: bool | None


class EnrollmentService:
    """Enroll and validate multiple face samples per student."""

    def __init__(
        self,
        student_repository: StudentRepository,
        embedding_repository: FaceEmbeddingRepository,
        audit_service: AuditService,
        face_engine: FaceEngine,
        image_quality_service: ImageQualityService,
        face_matcher: FaceMatcher,
        embedding_cache: EmbeddingCache,
        liveness_detector: LivenessDetector,
        settings: Settings,
    ) -> None:
        self.student_repository = student_repository
        self.embedding_repository = embedding_repository
        self.audit_service = audit_service
        self.face_engine = face_engine
        self.image_quality_service = image_quality_service
        self.face_matcher = face_matcher
        self.embedding_cache = embedding_cache
        self.liveness_detector = liveness_detector
        self.settings = settings

    async def analyze(self, *, image_payload: str, expected_pose: str | None = None) -> FaceAnalysisResult:
        image = decode_base64_image(image_payload)
        ensure_minimum_size(image)
        faces = await self.face_engine.detect(image)
        provider_name = getattr(self.face_engine, "provider_name", "unknown")
        pose_reliable = provider_name != "mock"

        if len(faces) != 1:
            return FaceAnalysisResult(
                provider_name=provider_name,
                pose_reliable=pose_reliable,
                faces_count=len(faces),
                primary_pose=None,
                detection_score=None,
                quality_score=None,
                expected_pose=expected_pose,
                pose_match=None,
            )

        face = faces[0]
        crop = crop_image(image, face.bbox)
        quality = self.image_quality_service.assess(crop, min_score=0.0)
        pose = face.pose or "front"
        pose_match = pose == expected_pose if expected_pose and pose_reliable else None
        return FaceAnalysisResult(
            provider_name=provider_name,
            pose_reliable=pose_reliable,
            faces_count=1,
            primary_pose=pose,
            detection_score=face.detection_score,
            quality_score=quality.score,
            expected_pose=expected_pose,
            pose_match=pose_match,
        )

    async def enroll(
        self,
        *,
        student_id: str,
        image_samples: list[tuple[str, str | None]],
        actor_id: str,
        tenant_id: str,
        campus_id: str | None = None,
    ) -> EnrollmentResult:
        resolved_campus_id = campus_id or self.settings.default_campus_id
        student = await self.student_repository.get_by_student_id(tenant_id, student_id)
        if student is None:
            raise NotFoundAppError("Student not found.")

        if not (self.settings.min_enrollment_samples <= len(image_samples) <= self.settings.max_enrollment_samples):
            raise ValidationAppError(
                f"Enrollment requires between {self.settings.min_enrollment_samples} and "
                f"{self.settings.max_enrollment_samples} samples."
            )

        gallery = await self.embedding_cache.get_scope_embeddings(tenant_id, resolved_campus_id)
        accepted: list[FaceEmbeddingDocument] = []
        rejected: list[SampleRejection] = []

        for index, (image_payload, requested_pose) in enumerate(image_samples):
            try:
                embedding = await self._process_sample(
                    tenant_id=tenant_id,
                    campus_id=resolved_campus_id,
                    student=student,
                    image_payload=image_payload,
                    requested_pose=requested_pose,
                    gallery=gallery + self._accepted_as_gallery(accepted),
                )
            except ConflictAppError:
                raise
            except ValidationAppError as exc:
                rejected.append(SampleRejection(index=index, reason=exc.detail))
                continue

            accepted.append(embedding)

        if len(accepted) < self.settings.min_enrollment_samples:
            raise ValidationAppError(
                f"At least {self.settings.min_enrollment_samples} high-quality face samples are required. "
                f"Only {len(accepted)} were accepted."
            )

        stored_embeddings = await self.embedding_repository.create_many(accepted)
        await self.student_repository.increment_embedding_count(tenant_id, student.student_id, len(stored_embeddings))
        self.embedding_cache.invalidate_scope(tenant_id, resolved_campus_id)
        await self.audit_service.record(
            tenant_id=tenant_id,
            campus_id=resolved_campus_id,
            actor_id=actor_id,
            action=AuditAction.FACE_ENROLLED.value,
            target_type="student",
            target_id=student.student_id,
            metadata={"enrolled_count": len(stored_embeddings), "rejected_count": len(rejected)},
        )

        return EnrollmentResult(student=student, enrolled_embeddings=stored_embeddings, rejected_samples=rejected)

    async def _process_sample(
        self,
        *,
        tenant_id: str,
        campus_id: str,
        student: StudentDocument,
        image_payload: str,
        requested_pose: str | None,
        gallery: list[GalleryEmbedding],
    ) -> FaceEmbeddingDocument:
        image = decode_base64_image(image_payload)
        ensure_minimum_size(image)
        faces = await self.face_engine.detect(image)
        if len(faces) != 1:
            raise ValidationAppError("Each enrollment sample must contain exactly one face.")

        face = faces[0]
        crop = crop_image(image, face.bbox)
        quality = self.image_quality_service.assess(crop, min_score=self.settings.min_face_quality_score)
        if not quality.is_acceptable:
            reason = ", ".join(quality.reasons) if quality.reasons else "low_quality"
            raise ValidationAppError(f"Enrollment quality check failed: {reason}")

        if self.settings.liveness_enabled:
            liveness = await self.liveness_detector.assess(crop)
            if not liveness.passed:
                raise ValidationAppError("Liveness verification failed.")

        embedding = await self.face_engine.embed(image, face)
        duplicate_gallery = [item for item in gallery if item.student_id != student.student_id]
        duplicate_match = self.face_matcher.find_best_match(embedding.vector, duplicate_gallery)
        if duplicate_match and duplicate_match.confidence >= self.settings.duplicate_face_threshold:
            raise ConflictAppError(
                f"Potential duplicate enrollment detected against student {duplicate_match.student_id} "
                f"(confidence={duplicate_match.confidence})."
            )

        same_student_gallery = [item for item in gallery if item.student_id == student.student_id]
        same_student_match = self.face_matcher.find_best_match(embedding.vector, same_student_gallery)
        if same_student_match and same_student_match.confidence >= 0.99:
            raise ValidationAppError("Face sample is redundant with an existing enrolled embedding.")

        now = utc_now()
        return FaceEmbeddingDocument(
            tenant_id=tenant_id,
            campus_id=campus_id,
            student_id=student.student_id,
            embedding_binary=bytes(embedding_to_binary(embedding.vector)),
            embedding_dim=embedding.embedding_dim,
            pose=requested_pose or embedding.pose or face.pose or "front",
            quality_score=quality.score,
            model_name=embedding.model_name,
            is_active=True,
            created_at=now,
        )

    @staticmethod
    def _accepted_as_gallery(embeddings: list[FaceEmbeddingDocument]) -> list[GalleryEmbedding]:
        gallery: list[GalleryEmbedding] = []
        for index, embedding in enumerate(embeddings):
            gallery.append(
                GalleryEmbedding(
                    embedding_id=embedding.id or f"pending-{index}",
                    student_id=embedding.student_id,
                    vector=binary_to_embedding(embedding.embedding_binary, embedding.embedding_dim),
                    pose=embedding.pose,
                    quality_score=embedding.quality_score,
                    model_name=embedding.model_name,
                )
            )
        return gallery
