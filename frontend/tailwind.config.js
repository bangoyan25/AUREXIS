/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./mocks/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // AUREXIS design tokens — dark institutional trading terminal
        aurexis: {
          bg:           "#0A0C10",
          surface:      "#0F1219",
          elevated:     "#141820",
          border:       "#1C2333",
          muted:        "#252D3D",
          text:         "#E4EAF4",
          subtle:       "#7A8BA6",
          faint:        "#3D4F6B",
          accent:       "#C8A84B",
          "accent-dim": "#7A6229",
          success:      "#16A34A",
          "success-dim":"#14532D",
          danger:       "#DC2626",
          "danger-dim": "#7F1D1D",
          warning:      "#D97706",
          "warning-dim":"#78350F",
          info:         "#2563EB",
          "info-dim":   "#1E3A5F",
        },
      },
      fontFamily: {
        sans:    ["Montserrat", "Inter", "system-ui", "sans-serif"],
        display: ["Cinzel", "Georgia", "serif"],
        mono:    ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      spacing: {
        sidebar: "220px",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "fade-in":    "fadeIn 0.15s ease-out",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(2px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
