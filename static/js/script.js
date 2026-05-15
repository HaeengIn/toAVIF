const MAX_FILES = 100;
const ACCEPTED_EXT = ["jpg", "jpeg", "png", "webp", "gif"];

const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const fileList = document.getElementById("file-list");
const status = document.getElementById("status");
const submitButton = document.getElementById("submit-button");

let selectedFiles = [];

const setStatus = (message, type = "") => {
  status.textContent = message;
  status.className = `status ${type}`;
};

const validFile = (file) => {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ACCEPTED_EXT.includes(ext);
};

const renderFiles = () => {
  fileList.innerHTML = "";
  selectedFiles.forEach((file) => {
    const li = document.createElement("li");
    li.textContent = `${file.name} (${Math.ceil(file.size / 1024)}KB)`;
    fileList.appendChild(li);
  });
};

const addFiles = (files) => {
  const incoming = Array.from(files).filter(validFile);
  if (incoming.length === 0) {
    setStatus("지원되는 이미지 파일만 업로드할 수 있어요.", "error");
    return;
  }

  const merged = [...selectedFiles, ...incoming].slice(0, MAX_FILES);
  if (selectedFiles.length + incoming.length > MAX_FILES) {
    setStatus(`최대 ${MAX_FILES}개까지 업로드할 수 있어요.`, "error");
  } else {
    setStatus(`${merged.length}개 파일이 준비됐어요.`, "ok");
  }

  selectedFiles = merged;
  renderFiles();
};

fileInput.addEventListener("change", (event) => addFiles(event.target.files));

["dragenter", "dragover"].forEach((name) => {
  dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((name) => {
  dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
  });
});

dropZone.addEventListener("drop", (event) => {
  addFiles(event.dataTransfer?.files ?? []);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (selectedFiles.length === 0) {
    setStatus("먼저 이미지를 추가해주세요.", "error");
    return;
  }

  const formData = new FormData();
  selectedFiles.forEach((file) => formData.append("files", file));

  submitButton.disabled = true;
  setStatus("변환 중이에요...", "loading");

  try {
    const response = await fetch("/convert", { method: "POST", body: formData });
    if (!response.ok) {
      const errorBody = await response.json();
      throw new Error(errorBody.detail ?? "변환에 실패했습니다.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "toavif-converted.zip";
    a.click();
    URL.revokeObjectURL(url);

    setStatus("완료! ZIP 파일 다운로드가 시작됐어요.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    submitButton.disabled = false;
  }
});
