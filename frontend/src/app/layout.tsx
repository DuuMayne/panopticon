import './globals.css';

export const metadata = {
  title: 'OCULUS',
  description: 'Security control monitoring',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="border-b border-[var(--border)] sticky top-0 z-50 bg-[var(--background)]">
          <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
            <div className="flex items-center gap-6">
              <a href="/" className="font-bold text-sm tracking-wider text-[var(--accent)]">OCULUS</a>
              <div className="flex items-center gap-4 text-xs">
                <a href="/" className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">Controls</a>
                <a href="/admin" className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">Admin</a>
              </div>
            </div>
            <span className="text-xs text-[var(--muted)]">Proof &gt; Posture</span>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
