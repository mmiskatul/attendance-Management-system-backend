const STUDENT_ID_PATTERN = /^[A-Za-z0-9]{3}-[A-Za-z0-9]{2}-[A-Za-z0-9]{3}$/;
const LIVE_CAPTURE_INTERVAL_MS = 1400;
const REGISTRATION_SCAN_STEPS = [
  { pose: "front", label: "Front", instruction: "Look straight at the camera." },
  { pose: "left", label: "Left", instruction: "Turn your face slightly to the left." },
  { pose: "right", label: "Right", instruction: "Turn your face slightly to the right." },
];

const state = {
  token: sessionStorage.getItem("attendance_token") || "",
  user: JSON.parse(sessionStorage.getItem("attendance_user") || "null"),
  registrationSamples: [],
  activeView: "register",
  registrationScan: {
    running: false,
    currentPose: null,
    poseReliable: null,
  },
};

const refs = {
  authScreen: document.getElementById("auth-screen"),
  dashboardScreen: document.getElementById("dashboard-screen"),
  sessionStatus: document.getElementById("session-status"),
  roleStatus: document.getElementById("role-status"),
  healthBadge: document.getElementById("health-badge"),
  resultOutput: document.getElementById("result-output"),
  resultRender: document.getElementById("result-render"),
  resultStatus: document.getElementById("result-status"),
  registrationStatusCard: document.getElementById("registration-status-card"),
  registerSampleCount: document.getElementById("register-sample-count"),
  registerSamples: document.getElementById("register-samples"),
  registerGuideBadge: document.getElementById("register-guide-badge"),
  registerGuideOverlay: document.getElementById("register-guide-overlay"),
  registerGuideTitle: document.getElementById("register-guide-title"),
  registerGuideMessage: document.getElementById("register-guide-message"),
  recognizeStreamStatus: document.getElementById("recognize-stream-status"),
  recognizeLastMatch: document.getElementById("recognize-last-match"),
  recognizeLiveBadge: document.getElementById("recognize-live-badge"),
  recognizeOverlay: document.getElementById("recognize-success-overlay"),
  recognizeOverlayIcon: document.getElementById("recognize-overlay-icon"),
  recognizeOverlayTitle: document.getElementById("recognize-overlay-title"),
  recognizeOverlayMessage: document.getElementById("recognize-overlay-message"),
  navButtons: Array.from(document.querySelectorAll("[data-view]")),
  viewPanels: Array.from(document.querySelectorAll("[data-view-panel]")),
  registerForm: document.getElementById("register-workflow-form"),
  studentIdInput: document.getElementById("register-student-id"),
};

const liveRecognition = {
  socket: null,
  loopHandle: null,
  active: false,
  configured: false,
  awaitingResult: false,
  pausedUntil: 0,
  overlayTimer: null,
};

let activeCameraController = null;

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function humanizeKey(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function isPrimitive(value) {
  return value === null || ["string", "number", "boolean"].includes(typeof value);
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function formatConfidence(value) {
  if (typeof value !== "number") {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function normalizeStudentId(value) {
  return String(value || "").trim().toUpperCase();
}

function isValidStudentId(value) {
  return STUDENT_ID_PATTERN.test(normalizeStudentId(value));
}

function setResult(status, payload) {
  refs.resultStatus.textContent = status;
  refs.resultStatus.classList.toggle("error", status.toLowerCase().includes("error"));
  refs.resultOutput.textContent =
    typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  renderResult(status, payload);
}

function renderResult(status, payload) {
  refs.resultRender.innerHTML = "";

  if (typeof payload === "string") {
    refs.resultRender.innerHTML = `<div class="empty-state">${escapeHtml(payload)}</div>`;
    return;
  }

  if (!payload || typeof payload !== "object") {
    refs.resultRender.innerHTML = `<div class="empty-state">${escapeHtml(String(payload))}</div>`;
    return;
  }

  const summaryEntries = Object.entries(payload).filter(([, value]) => isPrimitive(value));
  if (summaryEntries.length) {
    const summary = document.createElement("div");
    summary.className = "summary-grid";
    summaryEntries.forEach(([key, value]) => {
      summary.appendChild(summaryCard(key, value));
    });
    refs.resultRender.appendChild(summary);
  }

  Object.entries(payload).forEach(([key, value]) => {
    if (isPrimitive(value)) {
      return;
    }
    refs.resultRender.appendChild(renderBlock(key, value));
  });

  if (!summaryEntries.length && refs.resultRender.children.length === 0) {
    refs.resultRender.innerHTML = `<div class="empty-state">${escapeHtml(status)}</div>`;
  }
}

function summaryCard(label, value) {
  const card = document.createElement("article");
  card.className = "summary-card";
  card.innerHTML = `
    <span class="label">${escapeHtml(humanizeKey(label))}</span>
    <span class="value">${escapeHtml(formatValue(value))}</span>
  `;
  return card;
}

function renderBlock(title, value) {
  const block = document.createElement("section");
  block.className = "result-block";

  const heading = document.createElement("h3");
  heading.textContent = humanizeKey(title);
  block.appendChild(heading);

  if (Array.isArray(value)) {
    if (value.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No records returned.";
      block.appendChild(empty);
      return block;
    }

    if (value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
      block.appendChild(renderTable(value));
      return block;
    }

    const list = document.createElement("div");
    list.className = "result-list";
    value.forEach((item, index) => {
      const entry = document.createElement("div");
      entry.className = "result-item";
      entry.innerHTML = `<strong>Item ${index + 1}</strong><span>${escapeHtml(formatValue(item))}</span>`;
      list.appendChild(entry);
    });
    block.appendChild(list);
    return block;
  }

  if (value && typeof value === "object") {
    const summary = document.createElement("div");
    summary.className = "summary-grid";
    Object.entries(value).forEach(([key, nestedValue]) => {
      summary.appendChild(summaryCard(key, nestedValue));
    });
    block.appendChild(summary);
    return block;
  }

  const fallback = document.createElement("div");
  fallback.className = "empty-state";
  fallback.textContent = formatValue(value);
  block.appendChild(fallback);
  return block;
}

function renderTable(rows) {
  const tableWrap = document.createElement("div");
  tableWrap.className = "result-table-wrap";

  const table = document.createElement("table");
  table.className = "result-table";

  const headers = Array.from(
    rows.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set())
  );

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = humanizeKey(header);
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    headers.forEach((header) => {
      const td = document.createElement("td");
      td.textContent = formatValue(row[header]);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  return tableWrap;
}

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function apiFetch(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...authHeaders(),
    ...(options.headers || {}),
  };

  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let payload = null;

  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!response.ok) {
    if ([401, 403].includes(response.status) && state.token) {
      clearSession("Authentication expired. Login again to continue.");
    }
    throw new Error(
      typeof payload === "object"
        ? JSON.stringify(payload, null, 2)
        : payload || `${response.status} ${response.statusText}`
    );
  }

  return payload;
}

function formToObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function withOptionalFields(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== "" && value !== null && value !== undefined)
  );
}

function createCameraController({ videoId, canvasId, onCapture }) {
  const video = document.getElementById(videoId);
  const canvas = document.getElementById(canvasId);
  const context = canvas.getContext("2d");
  let stream = null;

  async function start() {
    if (activeCameraController && activeCameraController !== controller) {
      activeCameraController.stop();
    }
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    activeCameraController = controller;
  }

  function stop() {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
    video.pause();
    video.srcObject = null;
    if (activeCameraController === controller) {
      activeCameraController = null;
    }
  }

  function capture() {
    if (!stream || video.videoWidth === 0 || video.videoHeight === 0) {
      throw new Error("Start the camera before capturing.");
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageBase64 = canvas.toDataURL("image/jpeg", 0.9);
    if (typeof onCapture === "function") {
      onCapture(imageBase64);
    }
    return imageBase64;
  }

  function isRunning() {
    return Boolean(stream);
  }

  const controller = { start, stop, capture, isRunning };
  return controller;
}

function setScreen() {
  const authenticated = Boolean(state.token);
  refs.authScreen.classList.toggle("hidden", authenticated);
  refs.dashboardScreen.classList.toggle("hidden", !authenticated);
  refs.sessionStatus.textContent = authenticated ? "Authenticated" : "Not authenticated";
  refs.roleStatus.textContent = authenticated
    ? `${state.user?.username || "user"} (${state.user?.role || "session"})`
    : "Login required";

  const isAdmin = state.user?.role === "admin";
  document.getElementById("nav-register").disabled = authenticated ? !isAdmin : true;
  if (authenticated) {
    setActiveView(isAdmin ? state.activeView || "register" : "attendance");
  }
}

function setActiveView(view) {
  const isAdmin = state.user?.role === "admin";
  const resolvedView = !isAdmin && view === "register" ? "attendance" : view;
  state.activeView = resolvedView;

  refs.navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.view === resolvedView);
  });

  refs.viewPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === resolvedView);
  });
}

function renderRegistrationSamples() {
  const captured = new Set(state.registrationSamples.map((sample) => sample.pose));
  refs.registerSampleCount.textContent = `${captured.size} / ${REGISTRATION_SCAN_STEPS.length} captured`;
  refs.registerSamples.className = "scan-progress-grid";
  refs.registerSamples.innerHTML = REGISTRATION_SCAN_STEPS.map((step) => {
    const isCurrent = state.registrationScan.running && state.registrationScan.currentPose === step.pose;
    const isCaptured = captured.has(step.pose);
    const tone = isCaptured ? "success" : isCurrent ? "active" : "pending";
    const label = isCaptured ? "Captured" : isCurrent ? "Move now" : "Pending";
    return `
      <article class="scan-step-card ${tone}" data-step-card="${step.pose}">
        <strong>${escapeHtml(step.label)}</strong>
        <span>${escapeHtml(label)}</span>
      </article>
    `;
  }).join("");
}

function renderRegistrationStatus({ tone = "", title, message, student = null, enrollment = null } = {}) {
  if (!title) {
    refs.registrationStatusCard.className = "recognition-card empty-state";
    refs.registrationStatusCard.textContent =
      "The registration workflow will create the student record first, then enroll and store face embeddings in MongoDB.";
    return;
  }

  refs.registrationStatusCard.className = `recognition-card ${tone}`.trim();
  refs.registrationStatusCard.innerHTML = `
    <div class="recognition-card-header">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <div class="muted">${escapeHtml(message || "")}</div>
      </div>
      <span class="recognition-pill">${escapeHtml(student?.student_id || "--")}</span>
    </div>
    <div class="recognition-meta">
      <div>
        <span>Student</span>
        <strong>${escapeHtml(student?.full_name || "--")}</strong>
      </div>
      <div>
        <span>Department</span>
        <strong>${escapeHtml(student?.department || "--")}</strong>
      </div>
      <div>
        <span>Embeddings Stored</span>
        <strong>${escapeHtml(String(enrollment?.enrolled_count ?? "--"))}</strong>
      </div>
      <div>
        <span>Status</span>
        <strong>${escapeHtml(
          enrollment ? `Rejected ${enrollment.rejected_samples?.length || 0} sample(s)` : "Pending"
        )}</strong>
      </div>
    </div>
  `;
}

function setRegistrationGuideBadge(label, tone = "idle") {
  refs.registerGuideBadge.textContent = label;
  refs.registerGuideBadge.className = `live-badge ${tone}`;
}

function showRegistrationGuide({ title, message, tone = "" }) {
  refs.registerGuideTitle.textContent = title;
  refs.registerGuideMessage.textContent = message;
  refs.registerGuideOverlay.className = `recognize-overlay registration-guide-overlay ${tone}`.trim();
}

function hideRegistrationGuide() {
  refs.registerGuideOverlay.className = "recognize-overlay hidden registration-guide-overlay";
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function resetRegistrationWorkflow() {
  state.registrationSamples = [];
  state.registrationScan.running = false;
  state.registrationScan.currentPose = null;
  state.registrationScan.poseReliable = null;
  renderRegistrationSamples();
  setRegistrationGuideBadge("Ready", "idle");
  hideRegistrationGuide();
}

async function submitRegistrationWorkflow(raw) {
  const studentId = normalizeStudentId(raw.student_id);
  refs.studentIdInput.value = studentId;

  if (!isValidStudentId(studentId)) {
    throw new Error("Student ID must match the format XXX-XX-XXX.");
  }

  if (state.registrationSamples.length < REGISTRATION_SCAN_STEPS.length) {
    throw new Error("Front, left, and right face scans are required before registration.");
  }

  const registerPayload = withOptionalFields({
    full_name: raw.full_name,
    department: raw.department,
    batch: raw.batch,
    semester: raw.semester,
    email: raw.email,
    phone: raw.phone,
    barcode_value: studentId,
    campus_id: raw.campus_id,
  });
  const student = await apiFetch("/api/v1/students/register", {
    method: "POST",
    body: JSON.stringify(registerPayload),
  });

  const enrollment = await apiFetch("/api/v1/faces/enroll", {
    method: "POST",
    body: JSON.stringify(
      withOptionalFields({
        student_id: studentId,
        campus_id: raw.campus_id,
        samples: state.registrationSamples,
      })
    ),
  });

  return { student, enrollment };
}

async function analyzeRegistrationFrame(expectedPose) {
  const imageBase64 = registerCamera.capture();
  const analysis = await apiFetch("/api/v1/faces/analyze", {
    method: "POST",
    body: JSON.stringify({
      image_base64: imageBase64,
      expected_pose: expectedPose,
    }),
  });
  return { imageBase64, analysis };
}

async function captureRegistrationStep(step) {
  if (state.registrationScan.poseReliable === false) {
    for (let count = 3; count >= 1; count -= 1) {
      showRegistrationGuide({
        title: step.label,
        message: `${step.instruction} Capturing in ${count}...`,
      });
      await sleep(700);
      if (!state.registrationScan.running) {
        return null;
      }
    }
    return registerCamera.capture();
  }

  let stableMatches = 0;
  for (let attempt = 0; attempt < 24; attempt += 1) {
    showRegistrationGuide({
      title: step.label,
      message: `${step.instruction} Hold the position until it is detected.`,
    });
    await sleep(350);
    if (!state.registrationScan.running) {
      return null;
    }

    const { imageBase64, analysis } = await analyzeRegistrationFrame(step.pose);
    if (!state.registrationScan.running) {
      return null;
    }
    if (state.registrationScan.poseReliable === null) {
      state.registrationScan.poseReliable = analysis.pose_reliable;
      if (!analysis.pose_reliable) {
        showRegistrationGuide({
          title: step.label,
          message: "Pose verification is not available in the current face engine. Using guided countdown capture.",
        });
        await sleep(700);
        return await captureRegistrationStep(step);
      }
    }

    if (analysis.faces_count !== 1) {
      stableMatches = 0;
      showRegistrationGuide({
        title: step.label,
        message: "Keep exactly one face inside the frame.",
      });
      continue;
    }

    if (analysis.pose_match) {
      stableMatches += 1;
      showRegistrationGuide({
        title: step.label,
        message: `${step.label} detected. Hold still...`,
      });
      if (stableMatches >= 2) {
        return imageBase64;
      }
      continue;
    }

    stableMatches = 0;
    showRegistrationGuide({
      title: step.label,
      message: `Detected ${analysis.primary_pose || "unknown"} pose. Move until ${step.label.toLowerCase()} is detected.`,
    });
  }

  throw new Error(`Could not confirm the ${step.label.toLowerCase()} face position. Reset and try again.`);
}

async function runGuidedRegistrationScan(raw) {
  if (state.registrationScan.running) {
    return;
  }
  if (!registerCamera.isRunning()) {
    throw new Error("Start the camera before beginning the guided face scan.");
  }

  resetRegistrationWorkflow();
  state.registrationScan.running = true;
  renderRegistrationStatus({
    title: "Guided Scan In Progress",
    message: "Follow the on-screen directions. Registration will submit automatically after the right-side scan.",
  });

  try {
    for (const step of REGISTRATION_SCAN_STEPS) {
      state.registrationScan.currentPose = step.pose;
      renderRegistrationSamples();
      showRegistrationGuide({
        title: step.label,
        message: step.instruction,
      });
      setRegistrationGuideBadge(step.label, "scanning");
      const imageBase64 = await captureRegistrationStep(step);
      if (!imageBase64) {
        return;
      }
      state.registrationSamples.push({
        image_base64: imageBase64,
        pose: step.pose,
      });
      renderRegistrationSamples();
      showRegistrationGuide({
        title: `${step.label} Captured`,
        message: "Hold steady while the next step loads.",
      });
      setRegistrationGuideBadge("Captured", "success");
      await sleep(500);
      if (!state.registrationScan.running) {
        return;
      }
    }

    state.registrationScan.currentPose = null;
    setRegistrationGuideBadge("Saving", "scanning");
    showRegistrationGuide({
      title: "Saving Registration",
      message: "Student record and face vectors are being stored now.",
    });

    const payload = await submitRegistrationWorkflow(raw);
    renderRegistrationStatus({
      tone: "state-success",
      title: "Registration Successful",
      message: "Student data saved and face embeddings stored successfully.",
      student: payload.student,
      enrollment: payload.enrollment,
    });
    setResult("Registration Successful", payload);
    setRegistrationGuideBadge("Success", "success");
    showRegistrationGuide({
      title: "Registration Successful",
      message: `${payload.student.full_name} is fully enrolled.`,
      tone: "success",
    });
    refs.registerForm.reset();
  } catch (error) {
    renderRegistrationStatus({
      tone: "state-error",
      title: "Registration Error",
      message: error.message,
    });
    setResult("Registration Error", error.message);
    setRegistrationGuideBadge("Error", "error");
    showRegistrationGuide({
      title: "Registration Failed",
      message: error.message,
      tone: "error",
    });
    throw error;
  } finally {
    state.registrationScan.running = false;
    state.registrationScan.currentPose = null;
    renderRegistrationSamples();
  }
}

function setLiveBadge(label, tone = "idle") {
  refs.recognizeLiveBadge.textContent = label;
  refs.recognizeLiveBadge.className = `live-badge ${tone}`;
}

function setRecognitionStreamStatus(message) {
  refs.recognizeStreamStatus.textContent = message;
}

function hideRecognitionOverlay() {
  refs.recognizeOverlay.classList.add("hidden");
  refs.recognizeOverlay.classList.remove("duplicate");
}

function showRecognitionOverlay({ title, message, icon, duplicate = false }) {
  refs.recognizeOverlayTitle.textContent = title;
  refs.recognizeOverlayMessage.textContent = message;
  refs.recognizeOverlayIcon.textContent = icon;
  refs.recognizeOverlay.classList.toggle("duplicate", duplicate);
  refs.recognizeOverlay.classList.remove("hidden");
}

function scheduleOverlayHide(delaySeconds) {
  window.clearTimeout(liveRecognition.overlayTimer);
  liveRecognition.overlayTimer = window.setTimeout(() => {
    hideRecognitionOverlay();
    if (liveRecognition.active) {
      setLiveBadge("Scanning", "scanning");
    }
  }, delaySeconds * 1000);
}

function renderRecognitionCard(payload = null) {
  if (!payload) {
    refs.recognizeLastMatch.className = "recognition-card empty-state";
    refs.recognizeLastMatch.textContent = "Start the camera and live recognition to scan continuously.";
    return;
  }

  const toneByEvent = {
    recognized: "state-success",
    duplicate: "state-duplicate",
    error: "state-error",
    rejected: "state-error",
    rate_limited: "state-error",
  };
  const cardClass = toneByEvent[payload.event] || "";
  const student = payload.student || {};
  const record = payload.attendance_record || {};

  refs.recognizeLastMatch.className = `recognition-card ${cardClass}`.trim();
  refs.recognizeLastMatch.innerHTML = `
    <div class="recognition-card-header">
      <div>
        <strong>${escapeHtml(student.full_name || humanizeKey(payload.event || "live status"))}</strong>
        <div class="muted">${escapeHtml(payload.message || "Waiting for stream events.")}</div>
      </div>
      <span class="recognition-pill">${escapeHtml(payload.attendance_status || payload.event || "status")}</span>
    </div>
    <div class="recognition-meta">
      <div>
        <span>Student ID</span>
        <strong>${escapeHtml(student.student_id || "--")}</strong>
      </div>
      <div>
        <span>Confidence</span>
        <strong>${formatConfidence(payload.confidence_score)}</strong>
      </div>
      <div>
        <span>Device</span>
        <strong>${escapeHtml(payload.device_id || "--")}</strong>
      </div>
      <div>
        <span>Check In</span>
        <strong>${escapeHtml(record.check_in_time || "--")}</strong>
      </div>
    </div>
  `;
}

function buildSocketUrl(path, params) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL(`${protocol}//${window.location.host}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

function getRecognitionConfig() {
  const payload = withOptionalFields(formToObject(document.getElementById("recognize-form")));
  if (!payload.device_id) {
    throw new Error("Device ID is required before starting live recognition.");
  }
  return payload;
}

function startRecognitionLoop() {
  window.clearInterval(liveRecognition.loopHandle);
  liveRecognition.loopHandle = window.setInterval(() => {
    if (!liveRecognition.active || !liveRecognition.configured || liveRecognition.awaitingResult) {
      return;
    }
    if (Date.now() < liveRecognition.pausedUntil) {
      return;
    }
    if (!liveRecognition.socket || liveRecognition.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    if (!recognitionCamera.isRunning()) {
      return;
    }

    try {
      const imageBase64 = recognitionCamera.capture();
      liveRecognition.awaitingResult = true;
      liveRecognition.socket.send(
        JSON.stringify({
          type: "frame",
          image_base64: imageBase64,
          captured_at: new Date().toISOString(),
        })
      );
    } catch (error) {
      liveRecognition.awaitingResult = false;
      setLiveBadge("Camera Error", "error");
      renderRecognitionCard({ event: "error", message: error.message });
      setResult("Camera Error", error.message);
    }
  }, LIVE_CAPTURE_INTERVAL_MS);
}

function stopRecognitionLoop() {
  window.clearInterval(liveRecognition.loopHandle);
  liveRecognition.loopHandle = null;
  liveRecognition.awaitingResult = false;
}

function pauseRecognition(seconds) {
  liveRecognition.pausedUntil = Date.now() + seconds * 1000;
  scheduleOverlayHide(seconds);
}

function stopLiveRecognition({ preserveCard = false } = {}) {
  stopRecognitionLoop();
  liveRecognition.active = false;
  liveRecognition.configured = false;
  liveRecognition.pausedUntil = 0;
  window.clearTimeout(liveRecognition.overlayTimer);
  hideRecognitionOverlay();

  if (liveRecognition.socket) {
    const socket = liveRecognition.socket;
    liveRecognition.socket = null;
    if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
      socket.close(1000, "client-stop");
    }
  }

  setRecognitionStreamStatus("Socket disconnected");
  setLiveBadge("Idle", "idle");
  if (!preserveCard) {
    renderRecognitionCard();
  }
}

function handleLiveRecognitionEvent(payload) {
  if (payload.event === "processing") {
    setLiveBadge("Scanning", "scanning");
    return;
  }

  if (["recognized", "duplicate", "unknown", "rejected", "error", "rate_limited"].includes(payload.event)) {
    liveRecognition.awaitingResult = false;
  }

  switch (payload.event) {
    case "ready":
      setRecognitionStreamStatus(payload.message);
      setLiveBadge("Ready", "idle");
      break;
    case "configured":
      liveRecognition.configured = true;
      setRecognitionStreamStatus(
        `Live stream active for ${payload.device_id}${payload.campus_id ? ` @ ${payload.campus_id}` : ""}`
      );
      setLiveBadge("Scanning", "scanning");
      break;
    case "recognized":
      renderRecognitionCard(payload);
      setResult("Live Attendance", payload);
      setLiveBadge("Marked", "success");
      showRecognitionOverlay({
        title: "Attendance Taken",
        message: `${payload.student?.full_name || "Student"} (${payload.student?.student_id || "unknown"})`,
        icon: "\u2713",
      });
      pauseRecognition(payload.cooldown_seconds || 5);
      break;
    case "duplicate":
      renderRecognitionCard(payload);
      setResult("Live Attendance", payload);
      setLiveBadge("Duplicate", "warning");
      showRecognitionOverlay({
        title: "Already Marked",
        message: payload.message || "Attendance already exists for this student today.",
        icon: "!",
        duplicate: true,
      });
      pauseRecognition(payload.cooldown_seconds || 3);
      break;
    case "unknown":
      renderRecognitionCard(payload);
      setLiveBadge("Unknown", "warning");
      break;
    case "rejected":
      renderRecognitionCard(payload);
      setLiveBadge("Rejected", "error");
      break;
    case "rate_limited":
      renderRecognitionCard(payload);
      setResult("Live Recognition Error", payload);
      setLiveBadge("Rate Limited", "error");
      break;
    case "error":
      renderRecognitionCard(payload);
      setResult("Live Recognition Error", payload);
      setLiveBadge("Error", "error");
      break;
    case "pong":
      setRecognitionStreamStatus("Socket alive");
      break;
    default:
      break;
  }
}

async function startLiveRecognition() {
  if (!state.token) {
    setResult("Recognition Error", "Login before starting live recognition.");
    return;
  }

  const config = getRecognitionConfig();
  if (!recognitionCamera.isRunning()) {
    throw new Error("Start the camera before starting live recognition.");
  }

  stopLiveRecognition({ preserveCard: true });
  renderRecognitionCard({
    event: "configured",
    message: "Starting live attendance stream.",
    device_id: config.device_id,
    campus_id: config.campus_id || "--",
  });

  const socketUrl = buildSocketUrl("/api/v1/attendance/ws/recognize", { token: state.token });
  const socket = new WebSocket(socketUrl);
  liveRecognition.socket = socket;
  liveRecognition.active = true;
  liveRecognition.configured = false;
  liveRecognition.awaitingResult = false;
  liveRecognition.pausedUntil = 0;
  setRecognitionStreamStatus("Connecting to attendance stream...");
  setLiveBadge("Connecting", "idle");

  socket.addEventListener("open", () => {
    socket.send(
      JSON.stringify({
        type: "configure",
        device_id: config.device_id,
        campus_id: config.campus_id || null,
      })
    );
    startRecognitionLoop();
  });

  socket.addEventListener("message", (event) => {
    try {
      handleLiveRecognitionEvent(JSON.parse(event.data));
    } catch (error) {
      setLiveBadge("Error", "error");
      setResult("Live Recognition Error", error.message);
    }
  });

  socket.addEventListener("close", (event) => {
    stopRecognitionLoop();
    liveRecognition.socket = null;
    liveRecognition.active = false;
    liveRecognition.configured = false;

    if ([4401, 4403].includes(event.code)) {
      clearSession("Live recognition authorization expired. Login again.");
      return;
    }

    setRecognitionStreamStatus("Socket disconnected");
    if (event.code !== 1000) {
      setLiveBadge("Disconnected", "error");
      renderRecognitionCard({
        event: "error",
        message: "Live recognition connection closed. Start the stream again.",
      });
    } else {
      setLiveBadge("Idle", "idle");
    }
  });

  socket.addEventListener("error", () => {
    setRecognitionStreamStatus("Socket error");
    setLiveBadge("Error", "error");
  });
}

function clearSession(reason = "Authentication token removed from browser session storage.") {
  stopLiveRecognition({ preserveCard: true });
  resetRegistrationWorkflow();
  registerCamera.stop();
  recognitionCamera.stop();

  state.token = "";
  state.user = null;
  sessionStorage.removeItem("attendance_token");
  sessionStorage.removeItem("attendance_user");
  setScreen();
  setResult("Session Cleared", reason);
}

async function handleLogin(event) {
  event.preventDefault();
  const payload = withOptionalFields(formToObject(event.currentTarget));
  try {
    const response = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.token = response.access_token;
    state.user = response.user;
    sessionStorage.setItem("attendance_token", state.token);
    sessionStorage.setItem("attendance_user", JSON.stringify(response.user));
    setScreen();
    setResult("Login Success", response);
  } catch (error) {
    setResult("Login Error", error.message);
  }
}

async function handleRegistrationWorkflow(event) {
  event.preventDefault();
  if (!refs.registerForm.reportValidity()) {
    return;
  }
  const raw = formToObject(event.currentTarget);
  refs.studentIdInput.value = normalizeStudentId(raw.student_id);
  await runGuidedRegistrationScan(raw);
}

async function handleStudentLookup(event) {
  event.preventDefault();
  const { student_id: studentId } = formToObject(event.currentTarget);
  try {
    const response = await apiFetch(`/api/v1/students/${encodeURIComponent(normalizeStudentId(studentId))}`);
    setResult("Student Lookup", response);
  } catch (error) {
    setResult("Lookup Error", error.message);
  }
}

async function handleHistoryLookup(event) {
  event.preventDefault();
  const { student_id: studentId } = formToObject(event.currentTarget);
  try {
    const response = await apiFetch(`/api/v1/attendance/student/${encodeURIComponent(normalizeStudentId(studentId))}`);
    setResult("Attendance History", response);
  } catch (error) {
    setResult("History Error", error.message);
  }
}

async function handleDailyLookup(event) {
  event.preventDefault();
  const payload = withOptionalFields(formToObject(event.currentTarget));
  const params = new URLSearchParams(payload);
  try {
    const response = await apiFetch(`/api/v1/attendance/daily?${params.toString()}`);
    setResult("Daily Attendance", response);
  } catch (error) {
    setResult("Daily Error", error.message);
  }
}

async function handleAuditLookup(event) {
  event.preventDefault();
  const payload = withOptionalFields(formToObject(event.currentTarget));
  const params = new URLSearchParams(payload);
  try {
    const response = await apiFetch(`/api/v1/admin/audit-logs?${params.toString()}`);
    setResult("Audit Logs", response);
  } catch (error) {
    setResult("Audit Error", error.message);
  }
}

async function handleHealthCheck() {
  try {
    const response = await apiFetch("/api/v1/health");
    refs.healthBadge.textContent = response.status || "Unknown";
    setResult("Health", response);
  } catch (error) {
    refs.healthBadge.textContent = "Error";
    setResult("Health Error", error.message);
  }
}

const registerCamera = createCameraController({
  videoId: "register-video",
  canvasId: "register-canvas",
});

const recognitionCamera = createCameraController({
  videoId: "recognize-video",
  canvasId: "recognize-canvas",
});

document.getElementById("login-form").addEventListener("submit", handleLogin);
document.getElementById("register-workflow-form").addEventListener("submit", handleRegistrationWorkflow);
document.getElementById("student-form").addEventListener("submit", handleStudentLookup);
document.getElementById("history-form").addEventListener("submit", handleHistoryLookup);
document.getElementById("daily-form").addEventListener("submit", handleDailyLookup);
document.getElementById("audit-form").addEventListener("submit", handleAuditLookup);
document.getElementById("health-button").addEventListener("click", handleHealthCheck);
document.getElementById("logout-button").addEventListener("click", () => clearSession());

document.getElementById("focus-student-id").addEventListener("click", () => {
  refs.studentIdInput.focus();
});

refs.studentIdInput.addEventListener("input", () => {
  refs.studentIdInput.value = normalizeStudentId(refs.studentIdInput.value);
});

refs.navButtons.forEach((button) => {
  button.addEventListener("click", () => setActiveView(button.dataset.view));
});

document.getElementById("register-start-camera").addEventListener("click", async () => {
  try {
    await registerCamera.start();
    setRegistrationGuideBadge("Camera Ready", "idle");
    showRegistrationGuide({
      title: "Guided Face Scan",
      message: "Keep your face in the frame, then click Scan Face and Register Student.",
    });
  } catch (error) {
    setResult("Camera Error", error.message);
  }
});

document.getElementById("register-stop-camera").addEventListener("click", () => {
  resetRegistrationWorkflow();
  registerCamera.stop();
});

document.getElementById("register-start-guided-scan").addEventListener("click", async () => {
  try {
    await handleRegistrationWorkflow({ preventDefault() {}, currentTarget: refs.registerForm });
  } catch (error) {
    // Guided scan already renders its own error state.
  }
});

document.getElementById("register-reset-scan").addEventListener("click", () => {
  resetRegistrationWorkflow();
});

document.getElementById("recognize-start-camera").addEventListener("click", async () => {
  try {
    await recognitionCamera.start();
    setLiveBadge("Camera Ready", "idle");
    setRecognitionStreamStatus("Camera active. Start live recognition when ready.");
  } catch (error) {
    setResult("Camera Error", error.message);
  }
});

document.getElementById("recognize-stop-camera").addEventListener("click", () => {
  stopLiveRecognition({ preserveCard: true });
  recognitionCamera.stop();
  setLiveBadge("Idle", "idle");
  setRecognitionStreamStatus("Camera stopped");
});

document.getElementById("recognize-start-stream").addEventListener("click", async () => {
  try {
    await startLiveRecognition();
  } catch (error) {
    setResult("Recognition Error", error.message);
  }
});

document.getElementById("recognize-stop-stream").addEventListener("click", () => {
  stopLiveRecognition({ preserveCard: true });
});

window.addEventListener("beforeunload", () => {
  stopLiveRecognition({ preserveCard: true });
  resetRegistrationWorkflow();
  registerCamera.stop();
  recognitionCamera.stop();
});

resetRegistrationWorkflow();
renderRegistrationStatus();
renderRecognitionCard();
hideRecognitionOverlay();
setRecognitionStreamStatus("Socket disconnected");
setLiveBadge("Idle", "idle");
setScreen();
