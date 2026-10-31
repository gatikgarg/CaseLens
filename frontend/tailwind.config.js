export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      colors: { sidebar: "#F7F7F8", line: "#E8E8EA", ink: "#111113", muted: "#6B6B73" },
      boxShadow: { composer: "0 2px 12px rgba(0,0,0,0.06)" },
    },
  },
  plugins: [],
};

