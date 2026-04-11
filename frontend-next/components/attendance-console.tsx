"use client";

import {
  ChangeEvent,
  FormEvent,
  startTransition,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { apiRequest, buildWebSocketUrl } from "@/lib/api";
import type {
  AttendanceStreamEvent,
  AuthenticatedUser,
  AuditLogListResponse,
  DailyAttendanceResponse,
  FaceAnalyzeResponse,
  FaceEnrollmentResponse,
  FaceSamplePayload,
  LoginFormState,
  RecordsFormState,
  RegistrationFormState,
  StudentAttendanceResponse,
  StudentResponse,
  TokenResponse,
} from "@/lib/types";
import { ResultConsole } from "@/components/result-console";

const STUDENT_ID_PATTERN = /^[A-Za-z0-9]{3}-[A-Za-z0-9]{2}-[A-Za-z0-9]{3}$/;
const LIVE_CAPTURE_INTERVAL_MS = 1400;
const REGISTRATION_SCAN_STEPS = [
  { pose: "front", label: "Front", instruction: "Look straight at the camera." },
  { pose: "left", label: "Left", instruction: "Turn your face slightly to the left." },
  { pose: "right", label: "Right", instruction: "Turn your face slightly to the right." },
] as const;

type DashboardView = "register" | "attendance" | "records";
type Tone = "idle" | "scanning" | "success" | "warning" | "error";

interface RegistrationStatusState {
  tone: "" | "state-success" | "state-error";
  title: string;
  message: string;
  student?: StudentResponse | null;
  enrollment?: FaceEnrollmentResponse | null;
}

interface GuideState {
  visible: boolean;
  title: string;
  message: string;
  tone?: "" | "success" | "error";
}

interface BadgeState {
  label: string;
  tone: Tone;
}

interface RecognitionOverlayState {
  visible: boolean;
  title: string;
  message: string;
  icon: string;
  duplicate: boolean;
}

interface RecognitionCardState {
  event: string;
  message: string;
  device_id?: string | null;
  campus_id?: string | null;
  attendance_status?: string | null;
  confidence_score?: number | null;
  student?: StudentResponse | null;
  attendance_record?: AttendanceStreamEvent["attendance_record"];
}

interface RegistrationScanState {
  running: boolean;
  currentPose: string | null;
  poseReliable: boolean | null;
}

const defaultLoginForm: LoginFormState = {
  username: "",
  password: "",
  tenant_id: "",
};

const defaultRegistrationForm: RegistrationFormState = {
  student_id: "",
  full_name: "",
  department: "",
  batch: "",
  semester: "",
  email: "",
  phone: "",
  campus_id: "",
};

const defaultRecordsForm: RecordsFormState = {
  student_id: "",
  attendance_date: "",
  campus_id: "",
  skip: "0",
  limit: "25",
};

function normalizeStudentId(value: string): string {
  return value.trim().toUpperCase();
}

function isValidStudentId(value: string): boolean {
  return STUDENT_ID_PATTERN.test(normalizeStudentId(value));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatConfidence(value?: number | null): string {
  if (typeof value !== "number") {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function getInitialSession(): { token: string; user: AuthenticatedUser | null } {
  if (typeof window === "undefined") {
    return { token: "", user: null };
  }

  const token = window.sessionStorage.getItem("attendance_token") || "";
  const rawUser = window.sessionStorage.getItem("attendance_user");
  return {
    token,
    user: rawUser ? (JSON.parse(rawUser) as AuthenticatedUser) : null,
  };
}

export function AttendanceConsole() {
  const initialSession = useMemo(() => getInitialSession(), []);
  const [token, setToken] = useState(initialSession.token);
  const [user, setUser] = useState<AuthenticatedUser | null>(initialSession.user);
  const [activeView, setActiveView] = useState<DashboardView>(
    initialSession.user?.role === "operator" ? "attendance" : "register",
  );
  const [loginForm, setLoginForm] = useState<LoginFormState>(defaultLoginForm);
  const [registrationForm, setRegistrationForm] = useState<RegistrationFormState>(defaultRegistrationForm);
  const [attendanceForm, setAttendanceForm] = useState({ device_id: "terminal-1", campus_id: "" });
  const [studentLookupId, setStudentLookupId] = useState("");
  const [historyLookupId, setHistoryLookupId] = useState("");
  const [recordsForm, setRecordsForm] = useState<RecordsFormState>(defaultRecordsForm);
  const [healthStatus, setHealthStatus] = useState("Unknown");
  const [resultStatus, setResultStatus] = useState("Idle");
  const [resultPayload, setResultPayload] = useState<unknown>(
    "Login first, then use the dashboard workflows.",
  );
  const [registrationSamples, setRegistrationSamples] = useState<FaceSamplePayload[]>([]);
  const [registrationScan, setRegistrationScan] = useState<RegistrationScanState>({
    running: false,
    currentPose: null,
    poseReliable: null,
  });
  const [registrationGuide, setRegistrationGuide] = useState<GuideState>({
    visible: false,
    title: "Guided Face Scan",
    message: "Start the camera, keep your face in frame, then begin the scan.",
  });
  const [registrationBadge, setRegistrationBadge] = useState<BadgeState>({ label: "Ready", tone: "idle" });
  const [registrationStatus, setRegistrationStatus] = useState<RegistrationStatusState | null>(null);
  const [streamStatus, setStreamStatus] = useState("Socket disconnected");
  const [liveBadge, setLiveBadge] = useState<BadgeState>({ label: "Idle", tone: "idle" });
  const [recognitionCard, setRecognitionCard] = useState<RecognitionCardState | null>(null);
  const [recognitionOverlay, setRecognitionOverlay] = useState<RecognitionOverlayState>({
    visible: false,
    title: "Attendance Taken",
    message: "Waiting for the first match.",
    icon: "✓",
    duplicate: false,
  });

  const loginFormRef = useRef<HTMLFormElement>(null);
  const registrationFormRef = useRef<HTMLFormElement>(null);
  const registerVideoRef = useRef<HTMLVideoElement>(null);
  const registerCanvasRef = useRef<HTMLCanvasElement>(null);
  const recognizeVideoRef = useRef<HTMLVideoElement>(null);
  const recognizeCanvasRef = useRef<HTMLCanvasElement>(null);
  const activeCameraKeyRef = useRef<"register" | "recognize" | null>(null);
  const streamsRef = useRef<{ register: MediaStream | null; recognize: MediaStream | null }>({
    register: null,
    recognize: null,
  });
  const recognitionRef = useRef<{
    socket: WebSocket | null;
    loopHandle: number | null;
    awaitingResult: boolean;
    active: boolean;
    configured: boolean;
    pausedUntil: number;
    overlayTimer: number | null;
  }>({
    socket: null,
    loopHandle: null,
    awaitingResult: false,
    active: false,
    configured: false,
    pausedUntil: 0,
    overlayTimer: null,
  });
  const scanStateRef = useRef<RegistrationScanState>({
    running: false,
    currentPose: null,
    poseReliable: null,
  });

  function setResult(status: string, payload: unknown) {
    startTransition(() => {
      setResultStatus(status);
      setResultPayload(payload);
    });
  }

  function updateRegistrationStatus(state: RegistrationStatusState | null) {
    setRegistrationStatus(state);
  }

  function syncSession(nextToken: string, nextUser: AuthenticatedUser | null) {
    setToken(nextToken);
    setUser(nextUser);
    if (typeof window !== "undefined") {
      if (nextToken) {
        window.sessionStorage.setItem("attendance_token", nextToken);
      } else {
        window.sessionStorage.removeItem("attendance_token");
      }
      if (nextUser) {
        window.sessionStorage.setItem("attendance_user", JSON.stringify(nextUser));
      } else {
        window.sessionStorage.removeItem("attendance_user");
      }
    }
  }

  function getMediaElements(kind: "register" | "recognize") {
    return kind === "register"
      ? { video: registerVideoRef.current, canvas: registerCanvasRef.current }
      : { video: recognizeVideoRef.current, canvas: recognizeCanvasRef.current };
  }

  async function startCamera(kind: "register" | "recognize") {
    if (activeCameraKeyRef.current && activeCameraKeyRef.current !== kind) {
      stopCamera(activeCameraKeyRef.current);
    }

    const { video } = getMediaElements(kind);
    if (!video) {
      throw new Error("Camera element is not ready.");
    }

    if (streamsRef.current[kind]) {
      return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    streamsRef.current[kind] = stream;
    video.srcObject = stream;
    await video.play();
    activeCameraKeyRef.current = kind;
  }

  function stopCamera(kind: "register" | "recognize") {
    const stream = streamsRef.current[kind];
    const { video } = getMediaElements(kind);
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
    streamsRef.current[kind] = null;
    if (video) {
      video.pause();
      video.srcObject = null;
    }
    if (activeCameraKeyRef.current === kind) {
      activeCameraKeyRef.current = null;
    }
  }

  function cameraRunning(kind: "register" | "recognize") {
    return Boolean(streamsRef.current[kind]);
  }

  function captureFrame(kind: "register" | "recognize"): string {
    const { video, canvas } = getMediaElements(kind);
    if (!video || !canvas || video.videoWidth === 0 || video.videoHeight === 0) {
      throw new Error("Start the camera before capturing.");
    }

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas context is not available.");
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  function resetRegistrationWorkflow() {
    const nextState: RegistrationScanState = {
      running: false,
      currentPose: null,
      poseReliable: null,
    };
    scanStateRef.current = nextState;
    setRegistrationScan(nextState);
    setRegistrationSamples([]);
    setRegistrationBadge({ label: "Ready", tone: "idle" });
    setRegistrationGuide({
      visible: false,
      title: "Guided Face Scan",
      message: "Start the camera, keep your face in frame, then begin the scan.",
    });
  }

  async function submitRegistrationWorkflow(): Promise<{
    student: StudentResponse;
    enrollment: FaceEnrollmentResponse;
  }> {
    const studentId = normalizeStudentId(registrationForm.student_id);
    if (!isValidStudentId(studentId)) {
      throw new Error("Student ID must match the format XXX-XX-XXX.");
    }
    if (registrationSamples.length < REGISTRATION_SCAN_STEPS.length) {
      throw new Error("Front, left, and right face scans are required before registration.");
    }

    const student = await apiRequest<StudentResponse>(
      "/api/v1/students/register",
      {
        method: "POST",
        body: JSON.stringify({
          full_name: registrationForm.full_name,
          department: registrationForm.department,
          batch: registrationForm.batch,
          semester: registrationForm.semester,
          email: registrationForm.email,
          phone: registrationForm.phone,
          barcode_value: studentId,
          campus_id: registrationForm.campus_id || undefined,
        }),
      },
      token,
    );

    const enrollment = await apiRequest<FaceEnrollmentResponse>(
      "/api/v1/faces/enroll",
      {
        method: "POST",
        body: JSON.stringify({
          student_id: studentId,
          campus_id: registrationForm.campus_id || undefined,
          samples: registrationSamples,
        }),
      },
      token,
    );

    return { student, enrollment };
  }

  async function analyzeRegistrationFrame(expectedPose: string) {
    const imageBase64 = captureFrame("register");
    const analysis = await apiRequest<FaceAnalyzeResponse>(
      "/api/v1/faces/analyze",
      {
        method: "POST",
        body: JSON.stringify({
          image_base64: imageBase64,
          expected_pose: expectedPose,
        }),
      },
      token,
    );
    return { imageBase64, analysis };
  }

  async function captureRegistrationStep(step: (typeof REGISTRATION_SCAN_STEPS)[number]): Promise<string | null> {
    if (scanStateRef.current.poseReliable === false) {
      for (let count = 3; count >= 1; count -= 1) {
        setRegistrationGuide({
          visible: true,
          title: step.label,
          message: `${step.instruction} Capturing in ${count}...`,
        });
        await sleep(700);
        if (!scanStateRef.current.running) {
          return null;
        }
      }
      return captureFrame("register");
    }

    let stableMatches = 0;
    for (let attempt = 0; attempt < 24; attempt += 1) {
      setRegistrationGuide({
        visible: true,
        title: step.label,
        message: `${step.instruction} Hold the position until it is detected.`,
      });
      await sleep(350);
      if (!scanStateRef.current.running) {
        return null;
      }

      const { imageBase64, analysis } = await analyzeRegistrationFrame(step.pose);
      if (!scanStateRef.current.running) {
        return null;
      }

      if (scanStateRef.current.poseReliable === null) {
        if (!analysis.pose_reliable) {
          const fallbackState: RegistrationScanState = {
            ...scanStateRef.current,
            poseReliable: false,
          };
          scanStateRef.current = fallbackState;
          setRegistrationScan(fallbackState);
          setRegistrationGuide({
            visible: true,
            title: step.label,
            message:
              "Pose verification is not available in the current face engine. Using guided countdown capture.",
          });
          await sleep(700);
          return captureRegistrationStep(step);
        }

        const reliableState: RegistrationScanState = {
          ...scanStateRef.current,
          poseReliable: true,
        };
        scanStateRef.current = reliableState;
        setRegistrationScan(reliableState);
      }

      if (analysis.faces_count !== 1) {
        stableMatches = 0;
        setRegistrationGuide({
          visible: true,
          title: step.label,
          message: "Keep exactly one face inside the frame.",
        });
        continue;
      }

      if (analysis.pose_match) {
        stableMatches += 1;
        setRegistrationGuide({
          visible: true,
          title: step.label,
          message: `${step.label} detected. Hold still...`,
        });
        if (stableMatches >= 2) {
          return imageBase64;
        }
        continue;
      }

      stableMatches = 0;
      setRegistrationGuide({
        visible: true,
        title: step.label,
        message: `Detected ${analysis.primary_pose || "unknown"} pose. Move until ${step.label.toLowerCase()} is detected.`,
      });
    }

    throw new Error(`Could not confirm the ${step.label.toLowerCase()} face position. Reset and try again.`);
  }

  async function runGuidedRegistrationScan() {
    if (!token) {
      throw new Error("Login before starting registration.");
    }
    if (scanStateRef.current.running) {
      return;
    }
    if (!cameraRunning("register")) {
      throw new Error("Start the camera before beginning the guided face scan.");
    }

    resetRegistrationWorkflow();
    const startedState: RegistrationScanState = {
      running: true,
      currentPose: null,
      poseReliable: null,
    };
    scanStateRef.current = startedState;
    setRegistrationScan(startedState);
    updateRegistrationStatus({
      tone: "",
      title: "Guided Scan In Progress",
      message: "Follow the on-screen directions. Registration will submit automatically after the right-side scan.",
    });

    try {
      const samples: FaceSamplePayload[] = [];
      for (const step of REGISTRATION_SCAN_STEPS) {
        const nextState: RegistrationScanState = {
          ...scanStateRef.current,
          currentPose: step.pose,
        };
        scanStateRef.current = nextState;
        setRegistrationScan(nextState);
        setRegistrationBadge({ label: step.label, tone: "scanning" });
        setRegistrationGuide({
          visible: true,
          title: step.label,
          message: step.instruction,
        });

        const imageBase64 = await captureRegistrationStep(step);
        if (!imageBase64) {
          return;
        }

        samples.push({ image_base64: imageBase64, pose: step.pose });
        setRegistrationSamples([...samples]);
        setRegistrationGuide({
          visible: true,
          title: `${step.label} Captured`,
          message: "Hold steady while the next step loads.",
        });
        setRegistrationBadge({ label: "Captured", tone: "success" });
        await sleep(500);
        if (!scanStateRef.current.running) {
          return;
        }
      }

      setRegistrationBadge({ label: "Saving", tone: "scanning" });
      setRegistrationGuide({
        visible: true,
        title: "Saving Registration",
        message: "Student record and face vectors are being stored now.",
      });

      const payload = await submitRegistrationWorkflow();
      updateRegistrationStatus({
        tone: "state-success",
        title: "Registration Successful",
        message: "Student data saved and face embeddings stored successfully.",
        student: payload.student,
        enrollment: payload.enrollment,
      });
      setRegistrationBadge({ label: "Success", tone: "success" });
      setRegistrationGuide({
        visible: true,
        title: "Registration Successful",
        message: `${payload.student.full_name} is fully enrolled.`,
        tone: "success",
      });
      setResult("Registration Successful", payload);
      setRegistrationForm(defaultRegistrationForm);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Registration failed.";
      updateRegistrationStatus({
        tone: "state-error",
        title: "Registration Error",
        message,
      });
      setRegistrationBadge({ label: "Error", tone: "error" });
      setRegistrationGuide({
        visible: true,
        title: "Registration Failed",
        message,
        tone: "error",
      });
      setResult("Registration Error", message);
      throw error;
    } finally {
      const resetState: RegistrationScanState = {
        running: false,
        currentPose: null,
        poseReliable: scanStateRef.current.poseReliable,
      };
      scanStateRef.current = resetState;
      setRegistrationScan(resetState);
    }
  }

  function clearRecognitionOverlayLater(delaySeconds: number) {
    if (recognitionRef.current.overlayTimer) {
      window.clearTimeout(recognitionRef.current.overlayTimer);
    }
    recognitionRef.current.overlayTimer = window.setTimeout(() => {
      setRecognitionOverlay((current) => ({ ...current, visible: false }));
      if (recognitionRef.current.active) {
        setLiveBadge({ label: "Scanning", tone: "scanning" });
      }
    }, delaySeconds * 1000);
  }

  function stopLiveRecognition(preserveCard = false) {
    const recognition = recognitionRef.current;
    recognition.active = false;
    recognition.configured = false;
    recognition.awaitingResult = false;
    recognition.pausedUntil = 0;

    if (recognition.loopHandle) {
      window.clearInterval(recognition.loopHandle);
      recognition.loopHandle = null;
    }
    if (recognition.overlayTimer) {
      window.clearTimeout(recognition.overlayTimer);
      recognition.overlayTimer = null;
    }
    if (recognition.socket) {
      const socket = recognition.socket;
      recognition.socket = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, "client-stop");
      }
    }

    setStreamStatus("Socket disconnected");
    setLiveBadge({ label: "Idle", tone: "idle" });
    setRecognitionOverlay((current) => ({ ...current, visible: false }));
    if (!preserveCard) {
      setRecognitionCard(null);
    }
  }

  function handleLiveRecognitionEvent(payload: AttendanceStreamEvent) {
    if (payload.event === "processing") {
      setLiveBadge({ label: "Scanning", tone: "scanning" });
      return;
    }

    if (["recognized", "duplicate", "unknown", "rejected", "error", "rate_limited"].includes(payload.event)) {
      recognitionRef.current.awaitingResult = false;
    }

    switch (payload.event) {
      case "ready":
        setStreamStatus(payload.message);
        setLiveBadge({ label: "Ready", tone: "idle" });
        break;
      case "configured":
        recognitionRef.current.configured = true;
        setStreamStatus(
          `Live stream active for ${payload.device_id}${payload.campus_id ? ` @ ${payload.campus_id}` : ""}`,
        );
        setLiveBadge({ label: "Scanning", tone: "scanning" });
        break;
      case "recognized":
        setRecognitionCard(payload);
        setResult("Live Attendance", payload);
        setLiveBadge({ label: "Marked", tone: "success" });
        setRecognitionOverlay({
          visible: true,
          title: "Attendance Taken",
          message: `${payload.student?.full_name || "Student"} (${payload.student?.student_id || "unknown"})`,
          icon: "✓",
          duplicate: false,
        });
        recognitionRef.current.pausedUntil = Date.now() + ((payload.cooldown_seconds || 5) * 1000);
        clearRecognitionOverlayLater(payload.cooldown_seconds || 5);
        break;
      case "duplicate":
        setRecognitionCard(payload);
        setResult("Live Attendance", payload);
        setLiveBadge({ label: "Duplicate", tone: "warning" });
        setRecognitionOverlay({
          visible: true,
          title: "Already Marked",
          message: payload.message || "Attendance already exists for this student today.",
          icon: "!",
          duplicate: true,
        });
        recognitionRef.current.pausedUntil = Date.now() + ((payload.cooldown_seconds || 3) * 1000);
        clearRecognitionOverlayLater(payload.cooldown_seconds || 3);
        break;
      case "unknown":
        setRecognitionCard(payload);
        setLiveBadge({ label: "Unknown", tone: "warning" });
        break;
      case "rejected":
        setRecognitionCard(payload);
        setLiveBadge({ label: "Rejected", tone: "error" });
        break;
      case "rate_limited":
      case "error":
        setRecognitionCard(payload);
        setResult("Live Recognition Error", payload);
        setLiveBadge({ label: payload.event === "rate_limited" ? "Rate Limited" : "Error", tone: "error" });
        break;
      case "pong":
        setStreamStatus("Socket alive");
        break;
      default:
        break;
    }
  }

  async function startLiveRecognition() {
    if (!token) {
      throw new Error("Login before starting live recognition.");
    }
    if (!cameraRunning("recognize")) {
      throw new Error("Start the camera before starting live recognition.");
    }
    if (!attendanceForm.device_id.trim()) {
      throw new Error("Device ID is required before starting live recognition.");
    }

    stopLiveRecognition(true);
    setRecognitionCard({
      event: "configured",
      message: "Starting live attendance stream.",
      device_id: attendanceForm.device_id,
      campus_id: attendanceForm.campus_id || "--",
    });
    setStreamStatus("Connecting to attendance stream...");
    setLiveBadge({ label: "Connecting", tone: "idle" });

    const socket = new WebSocket(
      buildWebSocketUrl("/api/v1/attendance/ws/recognize", {
        token,
      }),
    );
    recognitionRef.current.socket = socket;
    recognitionRef.current.active = true;
    recognitionRef.current.configured = false;
    recognitionRef.current.awaitingResult = false;
    recognitionRef.current.pausedUntil = 0;

    socket.addEventListener("open", () => {
      socket.send(
        JSON.stringify({
          type: "configure",
          device_id: attendanceForm.device_id,
          campus_id: attendanceForm.campus_id || null,
        }),
      );

      recognitionRef.current.loopHandle = window.setInterval(() => {
        if (
          !recognitionRef.current.active ||
          !recognitionRef.current.configured ||
          recognitionRef.current.awaitingResult ||
          Date.now() < recognitionRef.current.pausedUntil ||
          !cameraRunning("recognize") ||
          !recognitionRef.current.socket ||
          recognitionRef.current.socket.readyState !== WebSocket.OPEN
        ) {
          return;
        }

        try {
          const imageBase64 = captureFrame("recognize");
          recognitionRef.current.awaitingResult = true;
          recognitionRef.current.socket.send(
            JSON.stringify({
              type: "frame",
              image_base64: imageBase64,
              captured_at: new Date().toISOString(),
            }),
          );
        } catch (error) {
          recognitionRef.current.awaitingResult = false;
          setLiveBadge({ label: "Camera Error", tone: "error" });
          setResult("Camera Error", error instanceof Error ? error.message : "Camera error");
        }
      }, LIVE_CAPTURE_INTERVAL_MS);
    });

    socket.addEventListener("message", (event) => {
      try {
        handleLiveRecognitionEvent(JSON.parse(event.data) as AttendanceStreamEvent);
      } catch (error) {
        setLiveBadge({ label: "Error", tone: "error" });
        setResult("Live Recognition Error", error instanceof Error ? error.message : "Socket parse error");
      }
    });

    socket.addEventListener("close", (event) => {
      if (recognitionRef.current.loopHandle) {
        window.clearInterval(recognitionRef.current.loopHandle);
        recognitionRef.current.loopHandle = null;
      }
      recognitionRef.current.socket = null;
      recognitionRef.current.active = false;
      recognitionRef.current.configured = false;
      recognitionRef.current.awaitingResult = false;

      if ([4401, 4403].includes(event.code)) {
        clearSession("Live recognition authorization expired. Login again.");
        return;
      }

      setStreamStatus("Socket disconnected");
      if (event.code !== 1000) {
        setLiveBadge({ label: "Disconnected", tone: "error" });
        setRecognitionCard({
          event: "error",
          message: "Live recognition connection closed. Start the stream again.",
        });
      } else {
        setLiveBadge({ label: "Idle", tone: "idle" });
      }
    });

    socket.addEventListener("error", () => {
      setStreamStatus("Socket error");
      setLiveBadge({ label: "Error", tone: "error" });
    });
  }

  function clearSession(reason = "Authentication token removed from browser session storage.") {
    stopLiveRecognition(true);
    resetRegistrationWorkflow();
    stopCamera("register");
    stopCamera("recognize");
    syncSession("", null);
    setActiveView("register");
    setResult("Session Cleared", reason);
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await apiRequest<TokenResponse>(
        "/api/v1/auth/login",
        {
          method: "POST",
          body: JSON.stringify({
            username: loginForm.username,
            password: loginForm.password,
            tenant_id: loginForm.tenant_id || undefined,
          }),
        },
      );
      syncSession(response.access_token, response.user);
      setActiveView(response.user.role === "operator" ? "attendance" : "register");
      setResult("Login Success", response);
    } catch (error) {
      setResult("Login Error", error instanceof Error ? error.message : "Login failed");
    }
  }

  async function handleStudentLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await apiRequest<StudentResponse>(
        `/api/v1/students/${encodeURIComponent(normalizeStudentId(studentLookupId))}`,
        {},
        token,
      );
      setResult("Student Lookup", response);
    } catch (error) {
      setResult("Lookup Error", error instanceof Error ? error.message : "Lookup failed");
    }
  }

  async function handleHistoryLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await apiRequest<StudentAttendanceResponse>(
        `/api/v1/attendance/student/${encodeURIComponent(normalizeStudentId(historyLookupId))}`,
        {},
        token,
      );
      setResult("Attendance History", response);
    } catch (error) {
      setResult("History Error", error instanceof Error ? error.message : "History lookup failed");
    }
  }

  async function handleDailyLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (recordsForm.attendance_date) {
      params.set("attendance_date", recordsForm.attendance_date);
    }
    if (recordsForm.campus_id) {
      params.set("campus_id", recordsForm.campus_id);
    }

    try {
      const response = await apiRequest<DailyAttendanceResponse>(
        `/api/v1/attendance/daily${params.toString() ? `?${params.toString()}` : ""}`,
        {},
        token,
      );
      setResult("Daily Attendance", response);
    } catch (error) {
      setResult("Daily Error", error instanceof Error ? error.message : "Daily lookup failed");
    }
  }

  async function handleAuditLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    params.set("skip", recordsForm.skip || "0");
    params.set("limit", recordsForm.limit || "25");

    try {
      const response = await apiRequest<AuditLogListResponse>(
        `/api/v1/admin/audit-logs?${params.toString()}`,
        {},
        token,
      );
      setResult("Audit Logs", response);
    } catch (error) {
      setResult("Audit Error", error instanceof Error ? error.message : "Audit lookup failed");
    }
  }

  async function handleHealthCheck() {
    try {
      const response = await apiRequest<{ status: string; [key: string]: unknown }>("/api/v1/health");
      setHealthStatus(response.status || "Unknown");
      setResult("Health", response);
    } catch (error) {
      setHealthStatus("Error");
      setResult("Health Error", error instanceof Error ? error.message : "Health check failed");
    }
  }

  function updateRegistrationField(event: ChangeEvent<HTMLInputElement>) {
    const { name, value } = event.target;
    setRegistrationForm((current) => ({
      ...current,
      [name]: name === "student_id" ? normalizeStudentId(value) : value,
    }));
  }

  function updateLoginField(event: ChangeEvent<HTMLInputElement>) {
    const { name, value } = event.target;
    setLoginForm((current) => ({ ...current, [name]: value }));
  }

  function updateAttendanceField(event: ChangeEvent<HTMLInputElement>) {
    const { name, value } = event.target;
    setAttendanceForm((current) => ({ ...current, [name]: value }));
  }

  function updateRecordsField(event: ChangeEvent<HTMLInputElement>) {
    const { name, value } = event.target;
    setRecordsForm((current) => ({ ...current, [name]: value }));
  }

  useEffect(() => {
    if (user?.role === "operator" && activeView === "register") {
      setActiveView("attendance");
    }
  }, [activeView, user]);

  useEffect(() => {
    return () => {
      stopLiveRecognition(true);
      stopCamera("register");
      stopCamera("recognize");
    };
  }, []);

  const registrationProgressText = `${registrationSamples.length} / ${REGISTRATION_SCAN_STEPS.length} captured`;
  const isAuthenticated = Boolean(token && user);
  const isAdmin = user?.role === "admin";

  const registrationCard = registrationStatus ? (
    <div className={`recognition-card ${registrationStatus.tone}`.trim()}>
      <div className="recognition-card-header">
        <div>
          <strong>{registrationStatus.title}</strong>
          <div className="muted">{registrationStatus.message}</div>
        </div>
        <span className="recognition-pill">{registrationStatus.student?.student_id || "--"}</span>
      </div>
      <div className="recognition-meta">
        <div>
          <span>Student</span>
          <strong>{registrationStatus.student?.full_name || "--"}</strong>
        </div>
        <div>
          <span>Department</span>
          <strong>{registrationStatus.student?.department || "--"}</strong>
        </div>
        <div>
          <span>Embeddings Stored</span>
          <strong>{registrationStatus.enrollment?.enrolled_count ?? "--"}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>
            {registrationStatus.enrollment
              ? `Rejected ${registrationStatus.enrollment.rejected_samples.length} sample(s)`
              : "Pending"}
          </strong>
        </div>
      </div>
    </div>
  ) : (
    <div className="recognition-card empty-state">
      The registration workflow will create the student record first, then enroll and store face embeddings in MongoDB.
    </div>
  );

  const recognitionCardView = recognitionCard ? (
    <div
      className={`recognition-card ${
        recognitionCard.event === "recognized"
          ? "state-success"
          : recognitionCard.event === "duplicate"
            ? "state-duplicate"
            : recognitionCard.event === "error" || recognitionCard.event === "rejected"
              ? "state-error"
              : ""
      }`.trim()}
    >
      <div className="recognition-card-header">
        <div>
          <strong>{recognitionCard.student?.full_name || recognitionCard.event}</strong>
          <div className="muted">{recognitionCard.message}</div>
        </div>
        <span className="recognition-pill">{recognitionCard.attendance_status || recognitionCard.event}</span>
      </div>
      <div className="recognition-meta">
        <div>
          <span>Student ID</span>
          <strong>{recognitionCard.student?.student_id || "--"}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{formatConfidence(recognitionCard.confidence_score)}</strong>
        </div>
        <div>
          <span>Device</span>
          <strong>{recognitionCard.device_id || "--"}</strong>
        </div>
        <div>
          <span>Check In</span>
          <strong>{recognitionCard.attendance_record?.check_in_time || "--"}</strong>
        </div>
      </div>
    </div>
  ) : (
    <div className="recognition-card empty-state">Start the camera and live recognition to scan continuously.</div>
  );

  return (
    <div className="app-shell">
      {!isAuthenticated ? (
        <section className="screen auth-screen">
          <div className="auth-hero">
            <p className="eyebrow">University Attendance Console</p>
            <h1>Face registration and realtime attendance from one backend.</h1>
            <p className="hero-copy">
              Login first. After authentication, the dashboard opens with a dedicated registration workflow where
              student details and facial embeddings are captured together.
            </p>
            <div className="auth-note">
              <strong>ID format:</strong>
              <code>XXX-XX-XXX</code>
            </div>
          </div>

          <div className="auth-card">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Authentication</p>
                <h2>Admin or Operator Login</h2>
              </div>
            </div>
            <form className="form-grid single" onSubmit={handleLogin} ref={loginFormRef}>
              <label>
                <span>Username</span>
                <input name="username" required value={loginForm.username} onChange={updateLoginField} />
              </label>
              <label>
                <span>Password</span>
                <input
                  name="password"
                  type="password"
                  required
                  value={loginForm.password}
                  onChange={updateLoginField}
                />
              </label>
              <label>
                <span>Tenant ID</span>
                <input name="tenant_id" value={loginForm.tenant_id} onChange={updateLoginField} />
              </label>
              <button className="primary-button" type="submit">
                Login to Dashboard
              </button>
            </form>
          </div>
        </section>
      ) : (
        <section className="screen dashboard-screen">
          <header className="dashboard-header panel">
            <div>
              <p className="eyebrow">University Attendance Dashboard</p>
              <h1>Registration, live recognition, and records in one workspace.</h1>
              <p className="hero-copy">
                Registration is the default workflow. Scan or type the student ID, guide the face through front,
                left, and right positions, then store the embeddings with the same record.
              </p>
            </div>

            <div className="hero-status">
              <div className="status-card">
                <span className="status-label">Session</span>
                <strong>Authenticated</strong>
                <span className="muted">
                  {user?.username} ({user?.role})
                </span>
              </div>
              <div className="status-card">
                <span className="status-label">API</span>
                <strong>{healthStatus}</strong>
                <div className="status-actions">
                  <button className="ghost-button" type="button" onClick={handleHealthCheck}>
                    Check Health
                  </button>
                  <button className="ghost-button" type="button" onClick={() => clearSession()}>
                    Logout
                  </button>
                </div>
              </div>
            </div>
          </header>

          <nav className="dashboard-nav panel">
            <button
              className={`nav-button${activeView === "register" ? " active" : ""}`}
              data-view="register"
              disabled={!isAdmin}
              onClick={() => setActiveView("register")}
              type="button"
            >
              Register
            </button>
            <button
              className={`nav-button${activeView === "attendance" ? " active" : ""}`}
              data-view="attendance"
              onClick={() => setActiveView("attendance")}
              type="button"
            >
              Live Attendance
            </button>
            <button
              className={`nav-button${activeView === "records" ? " active" : ""}`}
              data-view="records"
              onClick={() => setActiveView("records")}
              type="button"
            >
              Records
            </button>
          </nav>

          <div className="dashboard-layout">
            <main className="workspace">
              {activeView === "register" ? (
                <section className="panel workflow-panel">
                  <div className="panel-header">
                    <div>
                      <p className="eyebrow">Registration</p>
                      <h2>Student Registration With Guided Face Scan</h2>
                      <p className="muted">
                        Focus the student ID field and scan with a barcode scanner, or type manually. Accepted format:{" "}
                        <code>XXX-XX-XXX</code>.
                      </p>
                    </div>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => registrationFormRef.current?.querySelector<HTMLInputElement>("input")?.focus()}
                    >
                      Focus Student ID
                    </button>
                  </div>

                  <div className="workflow-grid">
                    <form className="form-grid" ref={registrationFormRef} onSubmit={(event) => event.preventDefault()}>
                      <label>
                        <span>Student ID / Scanned Barcode</span>
                        <input
                          name="student_id"
                          placeholder="ABC-12-XYZ"
                          pattern="[A-Za-z0-9]{3}-[A-Za-z0-9]{2}-[A-Za-z0-9]{3}"
                          required
                          value={registrationForm.student_id}
                          onChange={updateRegistrationField}
                        />
                      </label>
                      <label>
                        <span>Full Name</span>
                        <input name="full_name" required value={registrationForm.full_name} onChange={updateRegistrationField} />
                      </label>
                      <label>
                        <span>Department</span>
                        <input name="department" required value={registrationForm.department} onChange={updateRegistrationField} />
                      </label>
                      <label>
                        <span>Batch</span>
                        <input name="batch" required value={registrationForm.batch} onChange={updateRegistrationField} />
                      </label>
                      <label>
                        <span>Semester</span>
                        <input name="semester" required value={registrationForm.semester} onChange={updateRegistrationField} />
                      </label>
                      <label>
                        <span>Email</span>
                        <input name="email" type="email" required value={registrationForm.email} onChange={updateRegistrationField} />
                      </label>
                      <label>
                        <span>Phone</span>
                        <input name="phone" required value={registrationForm.phone} onChange={updateRegistrationField} />
                      </label>
                      <label>
                        <span>Campus ID</span>
                        <input name="campus_id" value={registrationForm.campus_id} onChange={updateRegistrationField} />
                      </label>
                    </form>

                    <div className="camera-stage">
                      <div className="panel-subheader">
                        <strong>Guided Face Scan</strong>
                        <span className="muted">{registrationProgressText}</span>
                      </div>
                      <div className="camera-shell">
                        <video className="camera-view" muted playsInline ref={registerVideoRef} />
                        <div className={`live-badge ${registrationBadge.tone}`}>{registrationBadge.label}</div>
                        <div
                          className={`recognize-overlay registration-guide-overlay${
                            registrationGuide.visible ? "" : " hidden"
                          }${registrationGuide.tone ? ` ${registrationGuide.tone}` : ""}`}
                        >
                          <strong>{registrationGuide.title}</strong>
                          <span>{registrationGuide.message}</span>
                        </div>
                      </div>
                      <canvas className="capture-canvas" ref={registerCanvasRef} />
                      <div className="camera-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={async () => {
                            try {
                              await startCamera("register");
                              setRegistrationBadge({ label: "Camera Ready", tone: "idle" });
                              setRegistrationGuide({
                                visible: true,
                                title: "Guided Face Scan",
                                message: "Keep your face in frame, then click Scan Face and Register Student.",
                              });
                            } catch (error) {
                              setResult("Camera Error", error instanceof Error ? error.message : "Camera start failed");
                            }
                          }}
                        >
                          Start Camera
                        </button>
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() => {
                            resetRegistrationWorkflow();
                            stopCamera("register");
                          }}
                        >
                          Stop Camera
                        </button>
                        <button className="ghost-button" type="button" onClick={resetRegistrationWorkflow}>
                          Reset Scan
                        </button>
                      </div>
                      <div className="scan-progress-grid">
                        {REGISTRATION_SCAN_STEPS.map((step) => {
                          const isCaptured = registrationSamples.some((sample) => sample.pose === step.pose);
                          const isCurrent = registrationScan.running && registrationScan.currentPose === step.pose;
                          const tone = isCaptured ? "success" : isCurrent ? "active" : "pending";
                          const label = isCaptured ? "Captured" : isCurrent ? "Move now" : "Pending";
                          return (
                            <article className={`scan-step-card ${tone}`} key={step.pose}>
                              <strong>{step.label}</strong>
                              <span>{label}</span>
                            </article>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {registrationCard}

                  <button
                    className="primary-button wide"
                    disabled={!isAdmin}
                    type="button"
                    onClick={async () => {
                      if (!registrationFormRef.current?.reportValidity()) {
                        return;
                      }
                      try {
                        await runGuidedRegistrationScan();
                      } catch {
                        // The guided workflow already updates the on-screen error state.
                      }
                    }}
                  >
                    Scan Face and Register Student
                  </button>
                </section>
              ) : null}

              {activeView === "attendance" ? (
                <section className="panel workflow-panel">
                  <div className="panel-header">
                    <div>
                      <p className="eyebrow">Attendance</p>
                      <h2>Realtime Recognition Terminal</h2>
                      <p className="muted">
                        The browser camera streams frames over WebSocket to the backend. A successful match shows a
                        large tick and the attendance status immediately on screen.
                      </p>
                    </div>
                  </div>

                  <form className="form-grid compact-header" onSubmit={(event) => event.preventDefault()}>
                    <label>
                      <span>Device ID</span>
                      <input name="device_id" required value={attendanceForm.device_id} onChange={updateAttendanceField} />
                    </label>
                    <label>
                      <span>Campus ID</span>
                      <input name="campus_id" value={attendanceForm.campus_id} onChange={updateAttendanceField} />
                    </label>
                  </form>

                  <div className="camera-stage">
                    <div className="camera-shell">
                      <video className="camera-view" muted playsInline ref={recognizeVideoRef} />
                      <div className={`live-badge ${liveBadge.tone}`}>{liveBadge.label}</div>
                      <div
                        className={`recognize-overlay${recognitionOverlay.visible ? "" : " hidden"}${
                          recognitionOverlay.duplicate ? " duplicate" : ""
                        }`}
                      >
                        <div className="overlay-icon">{recognitionOverlay.icon}</div>
                        <strong>{recognitionOverlay.title}</strong>
                        <span>{recognitionOverlay.message}</span>
                      </div>
                    </div>
                    <canvas className="capture-canvas" ref={recognizeCanvasRef} />
                    <div className="camera-actions">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={async () => {
                          try {
                            await startCamera("recognize");
                            setLiveBadge({ label: "Camera Ready", tone: "idle" });
                            setStreamStatus("Camera active. Start live recognition when ready.");
                          } catch (error) {
                            setResult("Camera Error", error instanceof Error ? error.message : "Camera start failed");
                          }
                        }}
                      >
                        Start Camera
                      </button>
                      <button
                        className="primary-button"
                        type="button"
                        onClick={async () => {
                          try {
                            await startLiveRecognition();
                          } catch (error) {
                            setResult(
                              "Recognition Error",
                              error instanceof Error ? error.message : "Live recognition start failed",
                            );
                          }
                        }}
                      >
                        Start Live Recognition
                      </button>
                      <button className="ghost-button" type="button" onClick={() => stopLiveRecognition(true)}>
                        Stop Live Recognition
                      </button>
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => {
                          stopLiveRecognition(true);
                          stopCamera("recognize");
                          setLiveBadge({ label: "Idle", tone: "idle" });
                          setStreamStatus("Camera stopped");
                        }}
                      >
                        Stop Camera
                      </button>
                    </div>
                    <div className="panel-subheader">
                      <strong>Live Recognition Status</strong>
                      <span className="muted">{streamStatus}</span>
                    </div>
                    {recognitionCardView}
                  </div>
                </section>
              ) : null}

              {activeView === "records" ? (
                <div className="records-grid">
                  <section className="panel">
                    <div className="panel-header">
                      <div>
                        <p className="eyebrow">Student</p>
                        <h2>Student Lookup</h2>
                      </div>
                    </div>
                    <form className="form-grid compact" onSubmit={handleStudentLookup}>
                      <label>
                        <span>Student ID</span>
                        <input value={studentLookupId} onChange={(event) => setStudentLookupId(normalizeStudentId(event.target.value))} />
                      </label>
                      <button className="secondary-button" type="submit">
                        Fetch Student
                      </button>
                    </form>
                  </section>

                  <section className="panel">
                    <div className="panel-header">
                      <div>
                        <p className="eyebrow">History</p>
                        <h2>Attendance Per Student</h2>
                      </div>
                    </div>
                    <form className="form-grid compact" onSubmit={handleHistoryLookup}>
                      <label>
                        <span>Student ID</span>
                        <input value={historyLookupId} onChange={(event) => setHistoryLookupId(normalizeStudentId(event.target.value))} />
                      </label>
                      <button className="secondary-button" type="submit">
                        Fetch History
                      </button>
                    </form>
                  </section>

                  <section className="panel">
                    <div className="panel-header">
                      <div>
                        <p className="eyebrow">Daily</p>
                        <h2>Daily Attendance</h2>
                      </div>
                    </div>
                    <form className="form-grid compact" onSubmit={handleDailyLookup}>
                      <label>
                        <span>Date</span>
                        <input name="attendance_date" type="date" value={recordsForm.attendance_date} onChange={updateRecordsField} />
                      </label>
                      <label>
                        <span>Campus ID</span>
                        <input name="campus_id" value={recordsForm.campus_id} onChange={updateRecordsField} />
                      </label>
                      <button className="secondary-button" type="submit">
                        Fetch Daily Attendance
                      </button>
                    </form>
                  </section>

                  <section className="panel">
                    <div className="panel-header">
                      <div>
                        <p className="eyebrow">Audit</p>
                        <h2>Administrative Logs</h2>
                      </div>
                    </div>
                    <form className="form-grid compact" onSubmit={handleAuditLookup}>
                      <label>
                        <span>Skip</span>
                        <input name="skip" type="number" min="0" value={recordsForm.skip} onChange={updateRecordsField} />
                      </label>
                      <label>
                        <span>Limit</span>
                        <input
                          name="limit"
                          type="number"
                          min="1"
                          max="200"
                          value={recordsForm.limit}
                          onChange={updateRecordsField}
                        />
                      </label>
                      <button className="secondary-button" type="submit">
                        Load Audit Logs
                      </button>
                    </form>
                  </section>
                </div>
              ) : null}
            </main>

            <aside className="console-column">
              <ResultConsole status={resultStatus} payload={resultPayload} />
            </aside>
          </div>
        </section>
      )}
    </div>
  );
}
