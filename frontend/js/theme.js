// ── Theme toggle — shared across all pages ────────────────────
(function() {
  const STORAGE_KEY = 'cc_theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const btns = document.querySelectorAll('.theme-toggle');
    btns.forEach(btn => { btn.textContent = theme === 'light' ? '🌙' : '☀️'; });
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }

  // Apply saved theme immediately (before paint)
  const saved = localStorage.getItem(STORAGE_KEY) || 'dark';
  applyTheme(saved);

  // Expose globally
  window.toggleTheme = toggleTheme;
  window.applyTheme  = applyTheme;

  // Wire up buttons after DOM loads
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(localStorage.getItem(STORAGE_KEY) || 'dark');
  });
})();