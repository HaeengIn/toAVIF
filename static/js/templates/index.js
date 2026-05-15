const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const convertButton = document.getElementById('convertButton');
const resetButton = document.getElementById('resetButton');
const settingsEl = document.getElementById('settings');
const resultEl = document.getElementById('result');
const progressBar = document.getElementById('progressBar');
const mouseGlow = document.getElementById('mouseGlow');

let selectedFiles = [];
let turnstilePassed = false;
let turnstileToken = '';
let glowTimer;

window.onTurnstileSuccess = function (token) {
  turnstilePassed = true;
  turnstileToken = token;
};

document.body.addEventListener('mousemove', (e) => {
  mouseGlow.style.left = `${e.clientX}px`;
  mouseGlow.style.top = `${e.clientY}px`;
  mouseGlow.style.opacity = '1';
  clearTimeout(glowTimer);
  glowTimer = setTimeout(() => { mouseGlow.style.opacity = '0'; }, 1500);
});

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag');
  setFiles(Array.from(e.dataTransfer.files));
});
fileInput.addEventListener('change', () => setFiles(Array.from(fileInput.files)));

function setFiles(files) {
  const allowed = ['jpg','jpeg','png','webp','gif'];
  for (const f of files) {
    const ext = f.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
      alert('지원하는 확장의 이미지가 아닌 경우 업로드할 수 없습니다.');
      return;
    }
  }
  selectedFiles = files.slice(0, 100);
  renderSettings();
}

function renderSettings() {
  settingsEl.innerHTML = `
    <div class="settings-row"><strong>전체 설정</strong><input id="gWidth" placeholder="너비"><input id="gHeight" placeholder="높이"><input id="gQuality" value="80" placeholder="품질"><label><input id="gStrip" type="checkbox" checked>메타삭제</label></div>
  `;
  selectedFiles.forEach((f, i) => {
    settingsEl.innerHTML += `<div class="settings-row"><span>${f.name}</span><input data-i="${i}" class="w"><input data-i="${i}" class="h"><input data-i="${i}" class="q" value="80"><label><input data-i="${i}" class="s" type="checkbox" checked>메타</label></div>`;
  });
}

convertButton.addEventListener('click', async () => {
  if (!turnstilePassed) return alert('캡챠 인증 후 업로드 해주세요.');
  if (!selectedFiles.length) return;
  const fd = new FormData();
  selectedFiles.forEach((f) => fd.append('files', f));
  fd.append('turnstile_token', turnstileToken);
  fd.append('global_width', document.getElementById('gWidth')?.value || '');
  fd.append('global_height', document.getElementById('gHeight')?.value || '');
  fd.append('global_quality', document.getElementById('gQuality')?.value || '80');
  fd.append('global_strip_metadata', document.getElementById('gStrip')?.checked ? 'true' : 'false');

  const per = {};
  selectedFiles.forEach((f, i) => {
    per[f.name] = {
      width: document.querySelector(`.w[data-i="${i}"]`)?.value || '',
      height: document.querySelector(`.h[data-i="${i}"]`)?.value || '',
      quality: document.querySelector(`.q[data-i="${i}"]`)?.value || '80',
      stripMetadata: document.querySelector(`.s[data-i="${i}"]`)?.checked ?? true
    };
  });
  fd.append('per_file_settings', JSON.stringify(per));

  progressBar.style.width = '30%';
  const res = await fetch('/api/convert', { method: 'POST', body: fd });
  progressBar.style.width = '80%';
  if (!res.ok) {
    const error = await res.json();
    alert(error.detail || '변환 실패');
    progressBar.style.width = '0%';
    return;
  }

  const data = await res.json();
  progressBar.style.width = '100%';
  resultEl.innerHTML = '';
  data.files.forEach((name) => {
    resultEl.innerHTML += `<a href="/api/download/${data.sessionId}/${name}">${name} 다운로드</a>`;
  });
  if (data.zipFile) {
    resultEl.innerHTML += `<a href="/api/download/${data.sessionId}/${data.zipFile}">ZIP 다운로드</a>`;
  }
  resetButton.classList.remove('hidden');
});

resetButton.addEventListener('click', () => {
  selectedFiles = [];
  settingsEl.innerHTML = '';
  resultEl.innerHTML = '';
  progressBar.style.width = '0%';
  resetButton.classList.add('hidden');
  fileInput.value = '';
});
