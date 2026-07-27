/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Arial', 'Helvetica Neue', 'Helvetica', 'sans-serif'],
        mono: ['IBM Plex Mono', 'Courier New', 'monospace'],
        display: ['Cormorant Garamond', 'Georgia', 'serif'],
      },
      colors: {
        brand: {
          navy:  '#0a1628',   // deep navy — primary dark surface
          blue:  '#1a56db',   // strong readable blue — links, accents, badges
          light: '#e8f0fb',   // very pale blue — subtle backgrounds only
          gray:  '#4b5563',   // mid grey — secondary text
          slate: '#f8f9fa',   // near-white — panel backgrounds
        },
        ui: {
          border:  '#000000', // all borders: sharp 1px black
          divider: '#e5e7eb', // internal dividers: light grey
          bg:      '#ffffff', // page background: pure white
          surface: '#f9fafb', // card / panel surface
          muted:   '#6b7280', // placeholder, hint text
        },
        status: {
          low:      '#1a56db', // LOW risk      — blue (not green neon)
          medium:   '#92400e', // MEDIUM risk   — dark amber (readable on white)
          high:     '#991b1b', // HIGH risk     — dark red (readable on white)
          critical: '#000000', // CRITICAL risk — black (maximum urgency, no neon)
          pass:     '#1a56db', // PASSED badge  — blue
          fail:     '#991b1b', // FAILED badge  — dark red
          clear:    '#1a56db', // CLEAR signal  — blue
          forged:   '#000000', // FORGED signal — black
        },
      },
      fontSize: {
        // explicit scale — nothing jumbo or decorative
        '2xs': ['10px', { lineHeight: '14px' }],
        xs:    ['11px', { lineHeight: '16px' }],
        sm:    ['12px', { lineHeight: '18px' }],
        base:  ['13px', { lineHeight: '20px' }],
        md:    ['14px', { lineHeight: '20px' }],
        lg:    ['16px', { lineHeight: '24px' }],
        xl:    ['18px', { lineHeight: '28px' }],
        '2xl': ['22px', { lineHeight: '30px' }],
        '3xl': ['28px', { lineHeight: '36px' }],
        '4xl': ['36px', { lineHeight: '44px' }],
        '5xl': ['48px', { lineHeight: '56px' }],
        // wordmark only
        wordmark: ['72px', { lineHeight: '80px', letterSpacing: '0.08em' }],
      },
      borderRadius: {
        // minimal — keep UI sharp and document-like
        none: '0px',
        sm:   '2px',
        DEFAULT: '3px',
        md:   '4px',
        // no 'lg', 'xl', '2xl', 'full' used — everything sharp
      },
      boxShadow: {
        // subtle depth only — no glows, no coloured shadows
        panel:  '0 1px 3px 0 rgba(0,0,0,0.08)',
        card:   '0 1px 2px 0 rgba(0,0,0,0.06)',
        border: 'inset 0 0 0 1px #000000',
        none:   'none',
      },
      animation: {
        // only functional animations — no glow, no pulse-glow
        'fade-in':   'fadeIn 0.15s ease-out',
        'slide-down':'slideDown 0.15s ease-out',
        'typewriter':'typewriter 1.5s steps(40) forwards',
        'blink':     'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideDown: {
          '0%':   { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        typewriter: {
          '0%':   { width: '0' },
          '100%': { width: '100%' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0' },
        },
        // scan kept but no glow — plain opacity shift only
        scan: {
          '0%':   { transform: 'translateY(0)',    opacity: '0.04' },
          '50%':  { opacity: '0.08' },
          '100%': { transform: 'translateY(100%)', opacity: '0.04' },
        },
      },
    },
  },
  plugins: [],
}