const MAX_FILES = 100;
const ACCEPTED = ["jpg", "jpeg", "png", "webp", "gif"];

const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const statusEl = document.getElementById("status");
const fileListEl = document.getElementById("file-list");
const resetButton = document.getElementById("reset-button");
const convertButton = document.getElementById("convert-button");

let selectedFiles = [];

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function getExt(fileName) {
  const split = fileName.toLowerCase().split(".");
  return split.length > 1 ? split.pop() : "";
}

function renderFileList() {
  fileListEl.innerHTML = "";
  selectedFiles.forEach((file, idx) => {
    const li = document.createElement("li");
    li.textContent = `${idx + 1}. ${file.name} (${Math.ceil(file.size / 1024)} KB)`;
    fileListEl.appendChild(li);
  });
}

function addFiles(files) {
  const nextFiles = [...selectedFiles];

  for (const file of files) {
    const ext = getExt(file.name);
    if (!ACCEPTED.includes(ext)) {
      setStatus(`지원하지 않는 확장자: ${file.name}`, true);
      continue;
    }
    if (nextFiles.length >= MAX_FILES) {
      setStatus(`최대 ${MAX_FILES}개까지 업로드할 수 있습니다.`, true);
      break;
    }
    nextFiles.push(file);
  }

  selectedFiles = nextFiles;
  renderFileList();
  if (selectedFiles.length > 0) {
    setStatus(`${selectedFiles.length}개 파일 선택됨`);
  }
}

function clearFiles() {
  selectedFiles = [];
  fileInput.value = "";
  renderFileList();
  setStatus("선택된 파일이 없습니다.");
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", (event) => {
  addFiles(event.target.files);
});

["dragenter", "dragover"].forEach((type) => {
  dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragover");
  });
});

["dragleave", "drop"].forEach((type) => {
  dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragover");
  });
});

dropZone.addEventListener("drop", (event) => {
  addFiles(event.dataTransfer.files);
});

resetButton.addEventListener("click", clearFiles);

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (selectedFiles.length === 0) {
    setStatus("업로드할 파일을 먼저 선택해 주세요.", true);
    return;
  }

  convertButton.disabled = true;
  setStatus("변환 중입니다. 잠시만 기다려주세요...");

  const formData = new FormData();
  selectedFiles.forEach((file) => formData.append("files", file));

  try {
    const response = await fetch("/api/convert", { method: "POST", body: formData });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "변환에 실패했습니다.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "toavif-converted.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    setStatus("변환 완료! ZIP 파일 다운로드가 시작됩니다.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    convertButton.disabled = false;
  }
});

setStatus("선택된 파일이 없습니다.");
