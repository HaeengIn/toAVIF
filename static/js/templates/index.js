const state = { files: [], settings: {} };
const allowed = ['jpg','jpeg','png','webp','gif'];
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const resultList = document.getElementById('resultList');

const uploadPanel = document.getElementById('uploadPanel');
const captchaPanel = document.getElementById('captchaPanel');

function showPopup(message){ alert(message); }

function validateFile(file){
  const ext = file.name.split('.').pop().toLowerCase();
  return allowed.includes(ext);
}

function renderFiles(){
  fileList.innerHTML = '';
  state.files.forEach(file => {
    const li = document.createElement('li');
    li.className = 'file-item';
    const s = state.settings[file.name] || {width:'',height:'',quality:60,strip_metadata:false};
    li.innerHTML = `<strong>${file.name}</strong>
      <div class="settings-row">
      <input class="input" data-key="width" data-file="${file.name}" type="number" min="1" value="${s.width ?? ''}" placeholder="너비">
      <input class="input" data-key="height" data-file="${file.name}" type="number" min="1" value="${s.height ?? ''}" placeholder="높이">
      <input class="input" data-key="quality" data-file="${file.name}" type="number" min="1" max="100" value="${s.quality}">
      <label><input data-key="strip_metadata" data-file="${file.name}" type="checkbox" ${s.strip_metadata ? 'checked' : ''}>메타데이터 삭제</label>
      </div>`;
    fileList.appendChild(li);
  });
}

document.addEventListener('change', (e)=>{
  const target = e.target;
  if(!target.dataset.file) return;
  const fileName = target.dataset.file;
  const key = target.dataset.key;
  state.settings[fileName] ||= { quality: 60, strip_metadata: false };
  state.settings[fileName][key] = target.type === 'checkbox' ? target.checked : target.value;
});

function addFiles(files){
  for (const file of files){
    if (state.files.length >= 100) break;
    if (!validateFile(file)) { showPopup('지원하지 않는 확장자입니다.'); continue; }
    state.files.push(file);
    state.settings[file.name] ||= { quality: 60, strip_metadata: false };
  }
  renderFiles();
}

['dragenter','dragover'].forEach(evt=>dropzone.addEventListener(evt, e=>{e.preventDefault(); dropzone.classList.add('dragging');}));
['dragleave','drop'].forEach(evt=>dropzone.addEventListener(evt, e=>{e.preventDefault(); dropzone.classList.remove('dragging');}));
dropzone.addEventListener('drop', e=> addFiles(e.dataTransfer.files));
dropzone.addEventListener('click', ()=> fileInput.click());
fileInput.addEventListener('change', e=> addFiles(e.target.files));

document.getElementById('applyGlobal').addEventListener('click', ()=>{
  const g = {
    width: document.getElementById('globalWidth').value,
    height: document.getElementById('globalHeight').value,
    quality: document.getElementById('globalQuality').value || 60,
    strip_metadata: document.getElementById('globalStrip').checked,
  };
  state.files.forEach(file => { state.settings[file.name] = { ...state.settings[file.name], ...g }; });
  renderFiles();
});

captchaPanel.addEventListener('click', ()=>{
  if (!window.turnstileToken) showPopup('캡챠 인증 후 업로드 해주세요.');
});

document.getElementById('convertBtn').addEventListener('click', async ()=>{
  if (!window.turnstileToken) return showPopup('캡챠 인증 후 업로드 해주세요.');
  if (state.files.length === 0) return showPopup('이미지를 먼저 업로드 해주세요.');

  document.getElementById('uploadProgress').style.width = '25%';
  const fd = new FormData();
  state.files.forEach(f => fd.append('files', f));
  fd.append('settings', JSON.stringify(state.settings));

  const res = await fetch('/api/convert', { method:'POST', body: fd });
  document.getElementById('uploadProgress').style.width = '100%';
  if(!res.ok){ showPopup((await res.json()).detail ?? '변환 실패'); return; }
  const data = await res.json();

  uploadPanel.classList.add('hidden');
  document.getElementById('resultPanel').classList.remove('hidden');
  document.getElementById('convertProgress').style.width = '100%';

  resultList.innerHTML = '';
  data.converted.forEach(item => {
    const li = document.createElement('li');
    li.className = 'file-item';
    li.innerHTML = `<span>${item.converted_name}</span><a class="btn" href="${item.download_url}">개별 다운로드</a>`;
    resultList.appendChild(li);
  });

  if (data.zip_url){
    const zip = document.getElementById('downloadZip');
    zip.href = data.zip_url;
    zip.classList.remove('hidden');
  }
});

document.getElementById('resetBtn').addEventListener('click', ()=> location.reload());

const glow = document.getElementById('cursorGlow');
let fadeTimer;
let visible = false;
document.body.addEventListener('mousemove', (e)=>{
  glow.style.left = `${e.clientX}px`;
  glow.style.top = `${e.clientY}px`;
  if (!visible) {
    glow.style.transition = 'opacity 1s ease';
    glow.style.opacity = '1';
    visible = true;
  }
  clearTimeout(fadeTimer);
  fadeTimer = setTimeout(()=>{
    glow.style.transition = 'opacity 1s ease';
    glow.style.opacity = '0';
    visible = false;
  }, 1500);
});

window.addEventListener('load', ()=>{
  const ok = !!window.turnstileToken;
  if (ok) {
    captchaPanel.classList.add('hidden');
    uploadPanel.classList.remove('hidden');
  }
});
setInterval(()=>{
  if (window.turnstileToken) {
    captchaPanel.classList.add('hidden');
    uploadPanel.classList.remove('hidden');
  }
}, 500);
