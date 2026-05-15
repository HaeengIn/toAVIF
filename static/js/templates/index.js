const state = {
  files: [],
  settings: {},
  turnstileToken: '',
  conversionId: null,
};

window.onTurnstileSuccess = (token) => {
  state.turnstileToken = token;
  document.getElementById('dropZone').classList.remove('disabled');
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

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (!state.turnstileToken) {
    alert('캡챠 인증 후 업로드 해주세요.');
    return;
  }
  handleFiles([...e.dataTransfer.files]);
});
fileInput.addEventListener('change', (e) => handleFiles([...e.target.files]));

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
    state.settings[String(state.files.length - 1)] = { width: '', height: '', quality: 70, remove_metadata: false };
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
        <label><input type='checkbox' data-key='remove_metadata' data-idx='${idx}' ${settings.remove_metadata ? 'checked' : ''}> 메타데이터 삭제</label>
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

document.getElementById('applyGlobalBtn').addEventListener('click', () => {
  const width = document.getElementById('globalWidth').value;
  const height = document.getElementById('globalHeight').value;
  const quality = document.getElementById('globalQuality').value || 70;
  const remove = document.getElementById('globalRemoveMetadata').checked;
  Object.keys(state.settings).forEach((k) => {
    state.settings[k] = { width, height, quality, remove_metadata: remove };
  });
  renderPreview();
});

convertBtn.addEventListener('click', async () => {
  if (!state.turnstileToken) return alert('캡챠 인증 후 업로드 해주세요.');
  if (state.files.length === 0) return alert('업로드된 파일이 없습니다.');

  uploadProgress.value = 25;
  const formData = new FormData();
  state.files.forEach((f) => formData.append('files', f));
  formData.append('settings_json', JSON.stringify(state.settings));
  formData.append('remove_metadata_all', document.getElementById('globalRemoveMetadata').checked ? 'true' : 'false');
  formData.append('turnstile_token', state.turnstileToken);

  uploadProgress.value = 60;
  convertProgress.value = 20;
  const resp = await fetch('/api/convert', { method: 'POST', body: formData });
  uploadProgress.value = 100;

  if (!resp.ok) {
    const errorData = await resp.json();
    alert(errorData.detail || '변환 중 오류가 발생했습니다.');
    return;
  }

  convertProgress.value = 100;
  downloadProgress.value = 35;
  const data = await resp.json();
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

  downloadProgress.value = 100;
  resultSection.classList.remove('hidden');
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
  uploadProgress.value = 0;
  convertProgress.value = 0;
  downloadProgress.value = 0;
});
