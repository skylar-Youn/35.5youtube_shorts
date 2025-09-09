export const metadata = {
  title: "Editor",
  description: "CapCut-like editor UI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body style={{ margin: 0, background: "#0b0d10", color: "#e8e8e8", fontFamily: "system-ui, -apple-system, Segoe UI, Roboto" }}>
        {children}
      </body>
    </html>
  );
}

