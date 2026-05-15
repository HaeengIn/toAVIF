(() => {
  const glow = document.getElementById('cursor-glow');
  if (!glow) return;
  let hideTimer;
  document.body.addEventListener('mousemove', (e) => {
    glow.style.left = `${e.clientX}px`;
    glow.style.top = `${e.clientY}px`;
    glow.style.opacity = '1';
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      glow.style.opacity = '0';
    }, 1500);
  });
})();
