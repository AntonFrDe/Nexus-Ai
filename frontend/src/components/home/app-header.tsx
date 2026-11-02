import Link from "next/link";

export function AppHeader({ children }: { children?: React.ReactNode }) {
  return (
    <header className="app-header">
      <Link href="/" className="brand">
        NEXUS
      </Link>
      <div className="app-header-center">{children}</div>
      <nav className="app-nav" aria-label="Navigation">
        <Link href="/">Projets</Link>
        <Link href="/settings">Réglages</Link>
        <Link href="/advanced">Mode avancé</Link>
      </nav>
    </header>
  );
}
