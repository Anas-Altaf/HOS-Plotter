import { useState, useRef } from "react";
import { ChevronLeft, ChevronRight, Printer, Download, Loader2 } from "lucide-react";
import type { DailyLog } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { LogSheet } from "./LogSheet";

interface Props {
  logs: DailyLog[];
}

export function LogSheets({ logs }: Props) {
  const [idx, setIdx] = useState(0);
  const [exporting, setExporting] = useState(false);
  const printAreaRef = useRef<HTMLDivElement>(null);

  if (!logs.length) return null;
  const cur = logs[idx];

  function handlePrint() {
    window.print();
  }

  async function handleExportPDF() {
    setExporting(true);
    try {
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const sheets = document.querySelectorAll<HTMLElement>(".pdf-sheet");
      if (!sheets.length) return;
      const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: "letter" });
      for (let i = 0; i < sheets.length; i++) {
        const canvas = await html2canvas(sheets[i], { scale: 2, backgroundColor: "#ffffff", useCORS: true });
        const img = canvas.toDataURL("image/png");
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const ratio = canvas.width / canvas.height;
        let w = pageWidth - 24;
        let h = w / ratio;
        if (h > pageHeight - 24) {
          h = pageHeight - 24;
          w = h * ratio;
        }
        const x = (pageWidth - w) / 2;
        const y = (pageHeight - h) / 2;
        if (i > 0) pdf.addPage();
        pdf.addImage(img, "PNG", x, y, w, h);
      }
      pdf.save("hos-logs.pdf");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 no-print">
        <div className="inline-flex items-center rounded-md border border-border bg-card overflow-hidden">
          <button
            type="button"
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            disabled={idx === 0}
            className="h-8 px-2.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="text-[12px] font-medium px-3 border-x border-border tabular-nums">
            Day {idx + 1} / {logs.length}
            <span className="text-muted-foreground font-normal ml-2 font-mono">{cur.date}</span>
          </span>
          <button
            type="button"
            onClick={() => setIdx((i) => Math.min(logs.length - 1, i + 1))}
            disabled={idx === logs.length - 1}
            className="h-8 px-2.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={handlePrint}>
            <Printer className="h-3.5 w-3.5" /> Print
          </Button>
          <Button size="sm" variant="outline" onClick={handleExportPDF} disabled={exporting}>
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            PDF
          </Button>
        </div>
      </div>

      {/* Visible: only the current sheet (paginated) */}
      <div ref={printAreaRef} className="print-area">
        <div className="pdf-sheet-wrap">
          <div className="pdf-sheet">
            <LogSheet log={cur} />
          </div>
        </div>

        {/* Hidden offscreen: all sheets, used by PDF export & print */}
        <div className="absolute -left-[9999px] top-0 w-[1100px]" aria-hidden>
          {logs.map((l, i) =>
            i === idx ? null : (
              <div key={l.date + i} className="pdf-sheet">
                <LogSheet log={l} />
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
