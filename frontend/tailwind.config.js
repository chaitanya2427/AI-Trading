/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: "#050508",
        cardBg: "rgba(18, 18, 24, 0.65)",
        borderDark: "rgba(255, 255, 255, 0.08)",
        profitGreen: "#30D158",
        lossRed: "#FF453A",
        warningYellow: "#FFD60A",
        brandBlue: "#2997FF",
        apple: {
          bg: "#000000",
          surface: "rgba(22, 22, 28, 0.6)",
          surfaceElevated: "rgba(30, 30, 38, 0.75)",
          border: "rgba(255, 255, 255, 0.1)",
          borderHover: "rgba(255, 255, 255, 0.22)",
          text: "#F5F5F7",
          subtext: "#86868B",
          muted: "#424245",
          blue: "#2997FF",
          green: "#30D158",
          red: "#FF453A",
          orange: "#FF9F0A",
          purple: "#BF5AF2",
        },
      },
      boxShadow: {
        'apple-3d': '0 20px 40px -15px rgba(0, 0, 0, 0.8), inset 0 1px 1px 0 rgba(255, 255, 255, 0.18)',
        'apple-3d-hover': '0 30px 60px -12px rgba(0, 0, 0, 0.9), inset 0 1px 1px 0 rgba(255, 255, 255, 0.3)',
        'apple-glow-blue': '0 0 30px -5px rgba(41, 151, 255, 0.4)',
        'apple-glow-green': '0 0 30px -5px rgba(48, 209, 88, 0.4)',
        'apple-glow-red': '0 0 30px -5px rgba(255, 69, 58, 0.4)',
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "SF Pro Text",
          "Helvetica Neue",
          "sans-serif"
        ],
        mono: [
          "SF Mono",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace"
        ]
      }
    },
  },
  plugins: [],
}
