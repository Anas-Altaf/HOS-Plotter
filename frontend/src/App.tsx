import { Routes, Route, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home";
import Result from "./pages/Result";

export default function App() {
  const location = useLocation();
  const isResult = location.pathname.startsWith("/result");

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-card/70 backdrop-blur no-print">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 h-12 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-5 w-5 rounded-sm bg-foreground grid place-items-center">
              <span className="text-[9px] font-bold text-background tracking-tight">HOS</span>
            </div>
            <span className="text-[13px] font-medium tracking-tight">HOS Plotter</span>
          </Link>
          <nav className="flex items-center gap-4 text-[12px]">
            {isResult && (
              <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
                New trip
              </Link>
            )}
            <a
              href="https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations"
              target="_blank"
              rel="noreferrer"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Reference
            </a>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/result" element={<Result />} />
        </Routes>
      </main>
      <footer className="border-t border-border py-3 no-print">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 text-[11px] text-muted-foreground flex items-center justify-between">
          <span>49 CFR 395.3 · Property-carrying driver</span>
          <span className="font-mono">v1.0</span>
        </div>
      </footer>
    </div>
  );
}
