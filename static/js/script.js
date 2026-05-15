(() => {
  const glow = document.getElementById('mouseGlow');
  if (!glow) return;
  let hideTimer;

  document.body.querySelectorAll('*').forEach((el) => {
    el.addEventListener('mousemove', (event) => {
      glow.style.left = `${event.clientX}px`;
      glow.style.top = `${event.clientY}px`;
      glow.style.opacity = '1';
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => {
        glow.style.opacity = '0';
      }, 2500);
    });
  });
})();
