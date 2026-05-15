const MAX_FILES = 100;
const ALLOWED_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp", "gif"]);

const form = document.getElementById("upload-form");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const summary = document.getElementById("summary");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");

let selectedFiles = [];

const getExtension = (fileName) => (fileName.split(".").pop() || "").toLowerCase();

const updateSummary = () => {
    if (!selectedFiles.length) {
        summary.textContent = "선택된 파일이 없습니다.";
        submitBtn.disabled = true;
        return;
    }

    const names = selectedFiles.map((file) => file.name).join(", ");
    summary.textContent = `${selectedFiles.length}개 파일 선택됨: ${names}`;
    submitBtn.disabled = false;
};

const setStatus = (message, type = "") => {
    statusEl.textContent = message;
    statusEl.className = `status ${type}`.trim();
};

const sanitizeFiles = (files) => {
    if (files.length > MAX_FILES) {
        setStatus(`한 번에 최대 ${MAX_FILES}개의 파일만 업로드할 수 있습니다.`, "error");
        return [];
    }

    const valid = files.filter((file) => ALLOWED_EXTENSIONS.has(getExtension(file.name)));
    if (valid.length !== files.length) {
        setStatus("지원하지 않는 확장자는 제외되었습니다. (jpg, jpeg, png, webp, gif)", "warn");
    } else {
        setStatus("");
    }

    return valid;
};

const assignFiles = (files) => {
    selectedFiles = sanitizeFiles(Array.from(files));
    updateSummary();
};

fileInput.addEventListener("change", (event) => {
    assignFiles(event.target.files);
});

["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        dropZone.classList.add("dragover");
    });
});

["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        dropZone.classList.remove("dragover");
    });
});

dropZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer?.files;
    if (files) {
        assignFiles(files);
    }
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!selectedFiles.length) {
        setStatus("업로드할 파일을 먼저 선택해 주세요.", "error");
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "변환 중...";
    setStatus("파일을 변환하고 있습니다...");

    const formData = new FormData();
    selectedFiles.forEach((file) => formData.append("files", file));

    try {
        const response = await fetch("/convert", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "변환 중 오류가 발생했습니다.");
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "toavif-converted.zip";
        link.click();
        URL.revokeObjectURL(url);

        setStatus("변환 완료! ZIP 파일 다운로드가 시작됩니다.", "success");
    } catch (error) {
        setStatus(error.message, "error");
    } finally {
        submitBtn.textContent = "AVIF로 변환하기";
        submitBtn.disabled = false;
    }
});
