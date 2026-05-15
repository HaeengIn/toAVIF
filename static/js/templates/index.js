const allowed = ['jpg','jpeg','png','webp','gif'];
let selectedFiles = [];
let currentJobId = null;

const dropZone = document.getElementById('drop-zone');
const input = document.getElementById('file-input');
const list = document.getElementById('file-list');
const convertBtn = document.getElementById('convert-btn');
const progress = document.getElementById('main-progress');
const result = document.getElementById('result');
const resetBtn = document.getElementById('reset-btn');

function popup(msg){ alert(msg); }
function ext(name){ return name.includes('.') ? name.split('.').pop().toLowerCase() : ''; }

function renderList(){
  list.innerHTML = '';
  selectedFiles.forEach((f, i) => {
    const el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = `<strong>${f.name}</strong>
    <div>개별 설정: 너비 <input type='number' min='1' data-i='${i}' data-k='width'>
    높이 <input type='number' min='1' data-i='${i}' data-k='height'>
    품질 <input type='number' min='1' max='100' value='80' data-i='${i}' data-k='quality'>
    <label><input type='checkbox' checked data-i='${i}' data-k='strip_metadata'> 메타데이터 삭제</label></div>`;
    list.appendChild(el);
  });
}

function validateAndSet(files){
  if(files.length > 100){ popup('최대 100개 이미지까지 업로드 가능합니다.'); return; }
  for(const f of files){ if(!allowed.includes(ext(f.name))){ popup('지원하지 않는 확장자 파일은 업로드할 수 없습니다.'); return; } }
  selectedFiles = Array.from(files);
  renderList();
}

dropZone.onclick = () => input.click();
input.onchange = (e) => validateAndSet(e.target.files);
dropZone.ondragover = (e) => { e.preventDefault(); };
dropZone.ondrop = (e) => { e.preventDefault(); validateAndSet(e.dataTransfer.files); };

convertBtn.onclick = async () => {
  const token = document.querySelector('[name="cf-turnstile-response"]')?.value;
  if (!token){ popup('캡챠 인증 후 업로드 해주세요.'); return; }
  if (selectedFiles.length === 0){ popup('업로드된 파일이 없습니다.'); return; }

  const form = new FormData();
  selectedFiles.forEach(f => form.append('files', f));
  form.append('turnstile_token', token);
  form.append('default_width', document.getElementById('default-width').value);
  form.append('default_height', document.getElementById('default-height').value);
  form.append('default_quality', document.getElementById('default-quality').value || '80');
  form.append('default_strip_metadata', document.getElementById('default-strip').checked ? 'true' : 'false');

  const overrides = {};
  list.querySelectorAll('input[data-i]').forEach(input => {
    const i = input.dataset.i; const k = input.dataset.k;
    overrides[i] ||= {};
    overrides[i][k] = input.type === 'checkbox' ? input.checked : input.value;
  });
  form.append('overrides', JSON.stringify(overrides));

  progress.value = 15;
  const res = await fetch('/api/convert', { method: 'POST', body: form });
  progress.value = 70;
  const data = await res.json();
  if(!res.ok){ popup(data.detail || '변환 실패'); return; }
  progress.value = 100;

  currentJobId = data.job_id;
  result.innerHTML = '<h3>변환 완료</h3>';
  data.files.forEach((name) => {
    const a = document.createElement('a');
    a.href = `/api/download/${currentJobId}/${encodeURIComponent(name)}`;
    a.textContent = `${name} 다운로드`;
    result.appendChild(a);
  });

  if (data.files.length >= 2){
    const z = document.createElement('a');
    z.href = `/api/download-zip/${currentJobId}`;
    z.textContent = 'ZIP 다운로드';
    result.appendChild(z);
  }
  resetBtn.hidden = false;
};

resetBtn.onclick = async () => {
  if (currentJobId) await fetch(`/api/reset/${currentJobId}`, { method: 'POST' });
  currentJobId = null;
  selectedFiles = [];
  list.innerHTML = '';
  result.innerHTML = '';
  progress.value = 0;
  resetBtn.hidden = true;
};
