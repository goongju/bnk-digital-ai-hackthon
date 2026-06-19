/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'bnk-bg':           'var(--bnk-bg)',
        'bnk-surface':      'var(--bnk-surface)',
        'bnk-surface-2':    'var(--bnk-surface-2)',
        'bnk-border':       'var(--bnk-border)',
        'bnk-text':         'var(--bnk-text)',
        'bnk-text-muted':   'var(--bnk-text-muted)',
        'bnk-text-faint':   'var(--bnk-text-faint)',
        'bnk-accent':       'var(--bnk-accent)',
        'bnk-accent-hover': 'var(--bnk-accent-hover)',
        'state-done':       'var(--state-done)',
        'state-running':    'var(--state-running)',
        'state-pending':    'var(--state-pending)',
        'state-degraded':   'var(--state-degraded)',
      },
      fontFamily: {
        pretendard: ['Pretendard', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

