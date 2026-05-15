const MAX_FILES = 100;
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadForm = document.getElementById("upload-form");
const convertBtn = document.getElementById("convert-btn");
const fileCount = document.getElementById("file-count");
const statusText = document.getElementById("status");

const dt = new DataTransfer();

const updateUI = () => {
  fileCount.textContent = `선택된 파일: ${dt.files.length}개`;
  convertBtn.disabled = dt.files.length === 0;
};

const setStatus = (message, isError = false) => {
  statusText.textContent = message;
  statusText.classList.toggle("error", isError);
};

const ingestFiles = (incomingFiles) => {
  const existing = Array.from(dt.files);
  const merged = [...existing, ...Array.from(incomingFiles)];

  if (merged.length > MAX_FILES) {
    setStatus(`한 번에 최대 ${MAX_FILES}개 파일만 업로드할 수 있어요.`, true);
    return;
  }

  dt.items.clear();
  for (const file of merged) {
    dt.items.add(file);
  }

  fileInput.files = dt.files;
  updateUI();
  setStatus("");
};

fileInput.addEventListener("change", (event) => {
  ingestFiles(event.target.files);
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-active");
  });
});

dropZone.addEventListener("drop", (event) => {
  ingestFiles(event.dataTransfer.files);
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!dt.files.length) {
    setStatus("파일을 먼저 선택해주세요.", true);
    return;
  }

  setStatus("변환 중입니다. 잠시만 기다려주세요...");
  convertBtn.disabled = true;

  const formData = new FormData();
  for (const file of dt.files) {
    formData.append("files", file);
  }

  try {
    const response = await fetch("/convert", { method: "POST", body: formData });

    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.detail || "변환 중 오류가 발생했습니다.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "toavif_results.zip";
    a.click();
    URL.revokeObjectURL(url);

    setStatus("변환 완료! ZIP 파일 다운로드를 시작합니다.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    convertBtn.disabled = false;
  }
});
