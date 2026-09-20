/* VidGrab Pro — downloader controller */

const $ = id => document.getElementById(id);

const state = {
  info: null,
  mode: 'video',
  formatId: null,
  formatLabel: 'Best',
  poll: null
};

/* ---------- Avatar menu ---------- */
const avatarBtn = $('avatarBtn'), avatarMenu = $('avatarMenu');
if (avatarBtn) {
  avatarBtn.onclick = e => { e.stopPropagation(); avatarMenu.classList.toggle('open'); };
  document.addEventListener('click', () => avatarMenu.classList.remove('open'));
}

/* ---------- Paste ---------- */
$('pasteBtn').onclick = async () => {
  try {
    const t = await navigator.clipboard.readText();
    if (t) { $('urlInput').value = t.trim(); $('urlInput').focus(); toast('Link pasted', 'info', 1500); }
  } catch { toast('Clipboard blocked — paste manually (Ctrl+V)', 'warn'); }
};

$('urlInput').addEventListener('keydown', e => { if (e.key === 'Enter') $('analyzeBtn').click(); });

/* ---------- Analyze ---------- */
$('analyzeBtn').onclick = async () => {
  const url = $('urlInput').value.trim();
  if (!url) { toast('Please paste a video link first', 'warn'); $('urlInput').focus(); return; }

  $('result').hidden = true;
  $('skeleton').hidden = false;
  $('skeleton').scrollIntoView({ behavior: 'smooth', block: 'center' });

  const btn = $('analyzeBtn');
  btn.classList.add('is-loading'); btn.disabled = true;

  try {
    const r = await fetch('/api/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);

    state.info = d;
    render(d);
    toast('Video found ✓', 'success', 2000);
  } catch (err) {
    toast(err.message || 'Could not analyze that link', 'error', 5000);
    $('skeleton').hidden = true;
  }

  btn.classList.remove('is-loading'); btn.disabled = false;
};

/* ---------- Render result ---------- */
function render(d) {
  $('skeleton').hidden = true;

  $('rThumb').src = d.thumbnail || '';
  $('rTitle').textContent = d.title;
  $('rAuthor').textContent = d.uploader;
  $('rViews').textContent = compact(d.views);
  $('rPlatform').textContent = d.platform;
  $('rDuration').textContent = clock(d.duration);

  const grid = $('qualityGrid');
  grid.innerHTML = '';

  d.formats.forEach((f, i) => {
    const card = document.createElement('button');
    card.className = 'q-card' + (i === 0 ? ' is-active' : '');
    card.innerHTML = `
      <span class="q-res">${f.label}${f.hd ? '<i class="fa-solid fa-certificate hd"></i>' : ''}</span>
      <span class="q-meta">${f.ext.toUpperCase()}${f.fps ? ' · ' + f.fps + 'fps' : ''}</span>
      <span class="q-size">${f.size}</span>`;
    card.onclick = () => {
      grid.querySelectorAll('.q-card').forEach(c => c.classList.remove('is-active'));
      card.classList.add('is-active');
      state.formatId = f.id;
      state.formatLabel = f.label;
    };
    grid.appendChild(card);
  });

  state.formatId = d.formats[0].id;
  state.formatLabel = d.formats[0].label;

  $('progressPanel').hidden = true;
  $('donePanel').hidden = true;
  $('downloadBtn').disabled = false;

  $('result').hidden = false;
  $('result').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/* ---------- Mode switch ---------- */
document.querySelectorAll('.seg').forEach(seg => {
  seg.onclick = () => {
    document.querySelectorAll('.seg').forEach(s => s.classList.remove('is-active'));
    seg.classList.add('is-active');
    state.mode = seg.dataset.mode;
    const audio = state.mode === 'audio';
    $('qualityWrap').hidden = audio;
    $('audioNote').hidden = !audio;
  };
});

/* ---------- Download ---------- */
$('downloadBtn').onclick = async () => {
  if (!state.info) return;

  const btn = $('downloadBtn');
  btn.disabled = true;
  $('donePanel').hidden = true;
  $('progressPanel').hidden = false;
  setProgress(0, 'Preparing…', '—', '—');

  try {
    const r = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: $('urlInput').value.trim(),
        type: state.mode,
        format_id: state.formatId,
        title: state.info.title,
        thumbnail: state.info.thumbnail,
        platform: state.info.platform,
        quality: state.mode === 'audio' ? 'MP3 192k' : state.formatLabel
      })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);

    state.poll = setInterval(() => track(d.job), 700);
  } catch (err) {
    toast(err.message || 'Download failed to start', 'error');
    $('progressPanel').hidden = true;
    btn.disabled = false;
  }
};

async function track(job) {
  try {
    const r = await fetch('/api/status/' + job);
    const s = await r.json();

    if (s.state === 'downloading') {
      setProgress(s.percent, 'Downloading…', s.speed, s.eta);
    } else if (s.state === 'processing') {
      setProgress(100, 'Merging & converting…', '—', '—');
    } else if (s.state === 'done') {
      clearInterval(state.poll);
      $('progressPanel').hidden = true;
      $('doneMeta').textContent = `${s.filename} · ${s.size}`;
      $('saveLink').href = '/api/file/' + job;
      $('saveLink').setAttribute('download', s.filename);
      $('donePanel').hidden = false;
      $('downloadBtn').disabled = false;
      toast('Download complete 🎉', 'success');
    } else if (s.state === 'error') {
      clearInterval(state.poll);
      $('progressPanel').hidden = true;
      $('downloadBtn').disabled = false;
      toast(s.error || 'Download failed', 'error', 6000);
    }
  } catch { /* keep polling */ }
}

function setProgress(pct, label, speed, eta) {
  $('pFill').style.width = pct + '%';
  $('pPercent').textContent = (Math.round(pct * 10) / 10) + '%';
  $('pState').textContent = label;
  $('pSpeed').textContent = speed;
  $('pEta').textContent = eta;
}

/* ---------- Utils ---------- */
function compact(n) {
  if (!n) return '0';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
}

function clock(s) {
  if (!s) return '—';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}`
           : `${m}:${String(x).padStart(2, '0')}`;
}

/* Nav scroll state */
addEventListener('scroll', () => {
  document.querySelector('.topbar')?.classList.toggle('scrolled', scrollY > 12);
});