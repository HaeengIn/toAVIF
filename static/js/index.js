const state = {
  files: [],
  settings: {},
  turnstileToken: '',
  conversionId: null,
};

const defaultQuality = 80;

window.onTurnstileSuccess = (token) => {
  state.turnstileToken = token;
};

const allowedExt = ['jpg', 'jpeg', 'png', 'webp', 'gif'];
const maxFiles = 100;

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const previewList = document.getElementById('previewList');
const convertBtn = document.getElementById('convertBtn');
const uploadProgress = document.getElementById('uploadProgress');
const convertProgress = document.getElementById('convertProgress');
const downloadProgress = document.getElementById('downloadProgress');
const resultSection = document.getElementById('resultSection');
const resultList = document.getElementById('resultList');
const zipDownloadBtn = document.getElementById('zipDownloadBtn');
const resetBtn = document.getElementById('resetBtn');

const globalWidthInput = document.getElementById('globalWidth');
const globalHeightInput = document.getElementById('globalHeight');
const globalQualityInput = document.getElementById('globalQuality');
const globalRemoveMetadataInput = document.getElementById('globalRemoveMetadata');
const applyGlobalBtn = document.getElementById('applyGlobalBtn');

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  handleFiles([...e.dataTransfer.files]);
});
fileInput.addEventListener('change', (e) => handleFiles([...e.target.files]));

function resetProgress() {
  uploadProgress.value = 0;
  convertProgress.value = 0;
  downloadProgress.value = 0;
}

function setProgress(phase) {
  if (phase === 'uploading') {
    uploadProgress.value = 60;
    convertProgress.value = 0;
    downloadProgress.value = 0;
  }
  if (phase === 'converting') {
    uploadProgress.value = 100;
    convertProgress.value = 65;
    downloadProgress.value = 0;
  }
  if (phase === 'preparing-download') {
    uploadProgress.value = 100;
    convertProgress.value = 100;
    downloadProgress.value = 70;
  }
  if (phase === 'done') {
    uploadProgress.value = 100;
    convertProgress.value = 100;
    downloadProgress.value = 100;
  }
}

function applyGlobalSettings() {
  const width = globalWidthInput.value;
  const height = globalHeightInput.value;
  const quality = globalQualityInput.value || defaultQuality;
  const remove = globalRemoveMetadataInput.checked;

  Object.keys(state.settings).forEach((k) => {
    state.settings[k] = { width, height, quality, remove_metadata: remove };
  });
  renderPreview();
}

function handleFiles(files) {
  const tooMany = state.files.length + files.length > maxFiles;
  if (tooMany) return alert(`최대 ${maxFiles}개 파일까지만 업로드할 수 있습니다.`);

  for (const file of files) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!allowedExt.includes(ext)) {
      alert(`지원하지 않는 확장자입니다: ${file.name}`);
      continue;
    }
    state.files.push(file);
    state.settings[String(state.files.length - 1)] = { width: '', height: '', quality: defaultQuality, remove_metadata: false };
  }
  renderPreview();
}

function renderPreview() {
  previewList.innerHTML = '';
  state.files.forEach((file, idx) => {
    const settings = state.settings[String(idx)];
    const wrap = document.createElement('div');
    wrap.className = 'preview-item';
    wrap.innerHTML = `<div>${file.name}</div>
      <div class='preview-controls'>
        <input type='number' data-key='width' data-idx='${idx}' value='${settings.width}' placeholder='너비'>
        <input type='number' data-key='height' data-idx='${idx}' value='${settings.height}' placeholder='높이'>
        <input type='number' data-key='quality' data-idx='${idx}' value='${settings.quality}' min='1' max='100' placeholder='퀄리티'>
        <label class='metadata-toggle'><input type='checkbox' data-key='remove_metadata' data-idx='${idx}' ${settings.remove_metadata ? 'checked' : ''}> 메타데이터 삭제</label>
      </div>`;
    previewList.appendChild(wrap);
  });

  previewList.querySelectorAll('input').forEach((input) => {
    input.addEventListener('change', () => {
      const idx = input.dataset.idx;
      const key = input.dataset.key;
      state.settings[idx][key] = input.type === 'checkbox' ? input.checked : input.value;
    });
  });
}

applyGlobalBtn.addEventListener('click', applyGlobalSettings);
[globalWidthInput, globalHeightInput, globalQualityInput, globalRemoveMetadataInput].forEach((input) => {
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      applyGlobalSettings();
    }
  });
});

convertBtn.addEventListener('click', async () => {
  if (!state.turnstileToken) return alert('캡챠 인증 후 변환을 시작해주세요.');
  if (state.files.length === 0) return alert('업로드된 파일이 없습니다.');

  resetProgress();
  setProgress('uploading');

  const formData = new FormData();
  state.files.forEach((f) => formData.append('files', f));
  formData.append('settings_json', JSON.stringify(state.settings));
  formData.append('remove_metadata_all', globalRemoveMetadataInput.checked ? 'true' : 'false');
  formData.append('turnstile_token', state.turnstileToken);

  try {
    const resp = await fetch('/api/convert', { method: 'POST', body: formData });

    if (!resp.ok) {
      const errorData = await resp.json();
      resetProgress();
      alert(errorData.detail || '변환 중 오류가 발생했습니다.');
      return;
    }

    setProgress('converting');
    const data = await resp.json();
    setProgress('preparing-download');

    state.conversionId = data.conversion_id;
    resultList.innerHTML = '';
    data.converted.forEach((item) => {
      const div = document.createElement('div');
      div.className = 'result-item';
      div.innerHTML = `<span>${item.converted_name}</span> <a class='btn' href='${item.download_url}'>개별 다운로드</a>`;
      resultList.appendChild(div);
    });

    if (data.zip_url) {
      zipDownloadBtn.classList.remove('hidden');
      zipDownloadBtn.href = data.zip_url;
    } else {
      zipDownloadBtn.classList.add('hidden');
    }

    setProgress('done');
    resultSection.classList.remove('hidden');
  } catch (error) {
    console.error(error);
    resetProgress();
    alert('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
  }
});

resetBtn.addEventListener('click', async () => {
  if (state.conversionId) {
    await fetch(`/api/reset/${state.conversionId}`, { method: 'POST' });
  }
  state.files = [];
  state.settings = {};
  state.conversionId = null;
  previewList.innerHTML = '';
  resultSection.classList.add('hidden');
  zipDownloadBtn.classList.add('hidden');
  resetProgress();
});
