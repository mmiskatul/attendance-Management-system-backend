export type UserRole = "admin" | "operator";

export interface AuthenticatedUser {
  _id?: string | null;
  tenant_id: string;
  username: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthenticatedUser;
}

export interface StudentResponse {
  _id?: string | null;
  tenant_id: string;
  campus_id: string;
  student_id: string;
  full_name: string;
  department: string;
  batch: string;
  semester: string;
  email: string;
  phone: string;
  status: string;
  barcode_value: string;
  face_embedding_count: number;
  created_at: string;
  updated_at: string;
}

export interface FaceEmbeddingResponse {
  id?: string | null;
  pose?: string | null;
  quality_score: number;
  model_name: string;
  created_at: string;
}

export interface RejectedSampleResponse {
  index: number;
  reason: string;
}

export interface FaceEnrollmentResponse {
  student: StudentResponse;
  enrolled_count: number;
  embeddings: FaceEmbeddingResponse[];
  rejected_samples: RejectedSampleResponse[];
}

export interface AttendanceRecordResponse {
  _id?: string | null;
  tenant_id: string;
  campus_id: string;
  student_id: string;
  attendance_date: string;
  attendance_session: string;
  check_in_time: string;
  device_id: string;
  confidence_score: number;
  attendance_status: string;
  matched_embedding_id?: string | null;
  created_at: string;
}

export interface AttendanceRecognizeResponse {
  recognized: boolean;
  student?: StudentResponse | null;
  confidence_score: number;
  attendance_status: string;
  matched_embedding_id?: string | null;
  attendance_record?: AttendanceRecordResponse | null;
  message: string;
}

export interface FaceAnalyzeResponse {
  provider_name: string;
  pose_reliable: boolean;
  faces_count: number;
  primary_pose?: string | null;
  detection_score?: number | null;
  quality_score?: number | null;
  expected_pose?: string | null;
  pose_match?: boolean | null;
}

export interface DailyAttendanceResponse {
  attendance_date: string;
  campus_id?: string | null;
  total_records: number;
  records: AttendanceRecordResponse[];
}

export interface StudentAttendanceResponse {
  student_id: string;
  records: AttendanceRecordResponse[];
}

export interface AuditLogResponse {
  _id?: string | null;
  tenant_id: string;
  campus_id?: string | null;
  actor_id: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  records: AuditLogResponse[];
  meta?: Record<string, unknown>;
}

export interface FaceSamplePayload {
  image_base64: string;
  pose?: string | null;
}

export interface AttendanceStreamEvent {
  event: string;
  message: string;
  device_id?: string | null;
  campus_id?: string | null;
  recognized?: boolean | null;
  confidence_score?: number | null;
  attendance_status?: string | null;
  matched_embedding_id?: string | null;
  student?: StudentResponse | null;
  attendance_record?: AttendanceRecordResponse | null;
  cooldown_seconds?: number | null;
}

export interface LoginFormState {
  username: string;
  password: string;
  tenant_id: string;
}

export interface RegistrationFormState {
  student_id: string;
  full_name: string;
  department: string;
  batch: string;
  semester: string;
  email: string;
  phone: string;
  campus_id: string;
}

export interface RecordsFormState {
  student_id: string;
  attendance_date: string;
  campus_id: string;
  skip: string;
  limit: string;
}
