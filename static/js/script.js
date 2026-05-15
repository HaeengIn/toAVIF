(() => {
  const glow = document.getElementById('mouseGlow');
  if (!glow) return;

  let hideTimer;

  const moveGlow = (event) => {
    glow.style.left = `${event.clientX}px`;
    glow.style.top = `${event.clientY}px`;
    glow.style.opacity = '1';
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      glow.style.opacity = '0';
    }, 2500);
  };

  document.addEventListener('mousemove', moveGlow);
})();
