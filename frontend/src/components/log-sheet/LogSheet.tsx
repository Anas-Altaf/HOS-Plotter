import { useMemo } from "react";
import type { DailyLog, DutyStatus } from "@/lib/types";

interface Props {
  log: DailyLog;
  driverInfo?: {
    carrier?: string;
    truckNumber?: string;
    homeTerminal?: string;
    mainOffice?: string;
  };
}

/**
 * Pure-SVG Driver's Daily Log. Re-creates the FMCSA grid layout from scratch.
 * No bitmap background — every pixel is generated, so alignment is exact at any
 * scale and prints clean.
 *
 * Coordinate system: 1100 x 720 viewBox.
 *   - Grid spans x in [GRID_X .. GRID_X + GRID_W], y in [GRID_Y .. GRID_Y + 4*ROW_H]
 *   - 24 hourly columns, each subdivided into 4 (15-min ticks)
 *   - Hour labels: Mid 1..11 Noon 1..11 Mid
 */

const VB_W = 1100;
const VB_H = 720;

const GRID_X = 110;
const GRID_W = 880;
const GRID_Y = 220;
const ROW_H = 36;
const GRID_H = ROW_H * 4;
const TOTALS_X = GRID_X + GRID_W + 10;
const TOTALS_W = 78;

const ROWS: { key: DutyStatus; label: string }[] = [
  { key: "OFF", label: "1. Off Duty" },
  { key: "SB", label: "2. Sleeper Berth" },
  { key: "D", label: "3. Driving" },
  { key: "ON", label: "4. On Duty (not driving)" },
];

const ROW_INDEX: Record<DutyStatus, number> = { OFF: 0, SB: 1, D: 2, ON: 3 };

const HOUR_LABELS = [
  "Mid", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
  "Noon", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "Mid",
];

function xForMin(min: number): number {
  return GRID_X + (Math.max(0, Math.min(1440, min)) / 1440) * GRID_W;
}

function yForRow(row: number): number {
  return GRID_Y + row * ROW_H + ROW_H / 2;
}

export function LogSheet({ log, driverInfo }: Props) {
  const [yyyy, mm, dd] = log.date.split("-");

  const linePoints = useMemo(() => {
    if (!log.segments.length) return "";
    const pts: string[] = [];
    let prev = ROW_INDEX[log.segments[0].status];
    pts.push(`${xForMin(log.segments[0].start_min)},${yForRow(prev)}`);
    for (const seg of log.segments) {
      const row = ROW_INDEX[seg.status];
      if (row !== prev) {
        pts.push(`${xForMin(seg.start_min)},${yForRow(prev)}`);
        pts.push(`${xForMin(seg.start_min)},${yForRow(row)}`);
        prev = row;
      }
      pts.push(`${xForMin(seg.end_min)},${yForRow(row)}`);
    }
    return pts.join(" ");
  }, [log.segments]);

  const r708 = log.recap?.["70_8"] || { A: 0, B: 0, C: 0 };
  const r607 = log.recap?.["60_7"] || { A: 0, B: 0, C: 0 };
  const grandTotal = (log.totals.OFF + log.totals.SB + log.totals.D + log.totals.ON);

  return (
    <div className="log-sheet bg-white border border-border rounded-md overflow-hidden">
      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        xmlns="http://www.w3.org/2000/svg"
        className="block w-full h-auto"
        role="img"
        aria-label={`Driver Daily Log for ${log.date}`}
      >
        <style>{`
          .ds-title { font: 700 22px Inter, system-ui, sans-serif; fill: #0f172a; }
          .ds-h    { font: 600 11px Inter, system-ui, sans-serif; fill: #0f172a; }
          .ds-sub  { font: 500 9.5px Inter, system-ui, sans-serif; fill: #475569; }
          .ds-row  { font: 600 10px Inter, system-ui, sans-serif; fill: #0f172a; }
          .ds-num  { font: 600 11px ui-monospace, "JetBrains Mono", monospace; fill: #0f172a; }
          .ds-numS { font: 500 9px ui-monospace, "JetBrains Mono", monospace; fill: #0f172a; }
          .ds-rem  { font: 500 8.5px Inter, system-ui, sans-serif; fill: #1f2937; }
          .ds-tick { stroke: #1f2937; stroke-width: 0.6; }
          .ds-grid { stroke: #1f2937; stroke-width: 0.8; fill: none; }
          .ds-thin { stroke: #1f2937; stroke-width: 0.5; fill: none; }
          .ds-line { stroke: #1d4ed8; stroke-width: 2.4; fill: none; stroke-linejoin: miter; stroke-linecap: butt; }
          .ds-box  { stroke: #1f2937; stroke-width: 0.8; fill: #ffffff; }
          .ds-fill { fill: #f8fafc; stroke: #1f2937; stroke-width: 0.5; }
          .ds-rule { stroke: #1f2937; stroke-width: 0.6; }
        `}</style>

        {/* Header */}
        <text x={40} y={48} className="ds-title">Driver's Daily Log</text>
        <text x={40} y={65} className="ds-sub">(24 hours)</text>

        {/* Date */}
        <g transform="translate(330, 30)">
          <text x={0} y={20} className="ds-num">{mm}</text>
          <line x1={-3} y1={28} x2={32} y2={28} className="ds-rule" />
          <text x={48} y={20} className="ds-num">{dd}</text>
          <line x1={45} y1={28} x2={80} y2={28} className="ds-rule" />
          <text x={96} y={20} className="ds-num">{yyyy}</text>
          <line x1={92} y1={28} x2={140} y2={28} className="ds-rule" />
          <text x={9} y={42} className="ds-sub">(month)</text>
          <text x={56} y={42} className="ds-sub">(day)</text>
          <text x={106} y={42} className="ds-sub">(year)</text>
        </g>

        {/* Original / Duplicate notes */}
        <text x={520} y={45} className="ds-sub">Original — File at home terminal.</text>
        <text x={520} y={60} className="ds-sub">Duplicate — Driver retains in his/her possession for 8 days.</text>

        {/* From / To */}
        <text x={40} y={100} className="ds-h">From:</text>
        <line x1={75} y1={102} x2={420} y2={102} className="ds-rule" />
        <text x={80} y={98} className="ds-num">{log.from_location}</text>
        <text x={440} y={100} className="ds-h">To:</text>
        <line x1={465} y1={102} x2={810} y2={102} className="ds-rule" />
        <text x={470} y={98} className="ds-num">{log.to_location}</text>

        {/* Total Miles + Total Mileage labels (placed in header band) */}
        <text x={40} y={135} className="ds-h">Total Miles Driving Today:</text>
        <line x1={195} y1={137} x2={310} y2={137} className="ds-rule" />
        <text x={200} y={133} className="ds-num">{log.total_miles_today.toFixed(1)}</text>

        <text x={340} y={135} className="ds-h">Total Mileage Today:</text>
        <line x1={460} y1={137} x2={560} y2={137} className="ds-rule" />
        <text x={465} y={133} className="ds-num">{log.total_miles_today.toFixed(1)}</text>

        <text x={600} y={135} className="ds-h">Carrier:</text>
        <line x1={640} y1={137} x2={1060} y2={137} className="ds-rule" />
        <text x={645} y={133} className="ds-num">{driverInfo?.carrier || ""}</text>

        {/* Truck / trailer */}
        <text x={40} y={165} className="ds-h">Truck/Trailer #:</text>
        <line x1={140} y1={167} x2={310} y2={167} className="ds-rule" />
        <text x={145} y={163} className="ds-num">{driverInfo?.truckNumber || ""}</text>

        <text x={340} y={165} className="ds-h">Main Office:</text>
        <line x1={415} y1={167} x2={700} y2={167} className="ds-rule" />
        <text x={420} y={163} className="ds-num">{driverInfo?.mainOffice || ""}</text>

        <text x={730} y={165} className="ds-h">Home Terminal:</text>
        <line x1={825} y1={167} x2={1060} y2={167} className="ds-rule" />
        <text x={830} y={163} className="ds-num">{driverInfo?.homeTerminal || ""}</text>

        {/* Grid frame */}
        <rect x={GRID_X} y={GRID_Y} width={GRID_W} height={GRID_H} className="ds-grid" />

        {/* Hour columns + 15-min ticks */}
        {Array.from({ length: 24 }).map((_, h) => {
          const x0 = GRID_X + (h / 24) * GRID_W;
          const x1 = GRID_X + ((h + 1) / 24) * GRID_W;
          return (
            <g key={`col-${h}`}>
              {/* full vertical hour line */}
              <line x1={x0} y1={GRID_Y} x2={x0} y2={GRID_Y + GRID_H} className="ds-grid" />
              {/* 15-min sub ticks: 3 inner ticks */}
              {[1, 2, 3].map((q) => {
                const xq = x0 + (q / 4) * (x1 - x0);
                return ROWS.map((_, rIdx) => {
                  const yTop = GRID_Y + rIdx * ROW_H;
                  const yBot = yTop + ROW_H;
                  // Half-row tick height; 30-min tick taller
                  const tickH = q === 2 ? ROW_H * 0.5 : ROW_H * 0.28;
                  return (
                    <g key={`tk-${h}-${q}-${rIdx}`}>
                      <line x1={xq} y1={yTop} x2={xq} y2={yTop + tickH} className="ds-tick" />
                      <line x1={xq} y1={yBot - tickH} x2={xq} y2={yBot} className="ds-tick" />
                    </g>
                  );
                });
              })}
            </g>
          );
        })}
        {/* close right edge */}
        <line x1={GRID_X + GRID_W} y1={GRID_Y} x2={GRID_X + GRID_W} y2={GRID_Y + GRID_H} className="ds-grid" />

        {/* Hour labels above grid */}
        {HOUR_LABELS.map((lbl, i) => {
          const x = GRID_X + (i / 24) * GRID_W;
          return (
            <text key={`hl-${i}`} x={x} y={GRID_Y - 6} textAnchor="middle" className="ds-sub">
              {lbl}
            </text>
          );
        })}

        {/* Row labels (left) and horizontal row separators */}
        {ROWS.map((r, i) => {
          const yTop = GRID_Y + i * ROW_H;
          return (
            <g key={`row-${r.key}`}>
              {i > 0 && (
                <line x1={GRID_X} y1={yTop} x2={GRID_X + GRID_W} y2={yTop} className="ds-grid" />
              )}
              <text x={GRID_X - 6} y={yTop + ROW_H / 2 + 3} textAnchor="end" className="ds-row">
                {r.label}
              </text>
            </g>
          );
        })}

        {/* Totals column header + cells */}
        <rect x={TOTALS_X} y={GRID_Y - 22} width={TOTALS_W} height={22} className="ds-fill" />
        <text x={TOTALS_X + TOTALS_W / 2} y={GRID_Y - 8} textAnchor="middle" className="ds-row">
          Total Hours
        </text>
        {ROWS.map((r, i) => {
          const y = GRID_Y + i * ROW_H;
          return (
            <g key={`tot-${r.key}`}>
              <rect x={TOTALS_X} y={y} width={TOTALS_W} height={ROW_H} className="ds-box" />
              <text
                x={TOTALS_X + TOTALS_W / 2}
                y={y + ROW_H / 2 + 4}
                textAnchor="middle"
                className="ds-num"
              >
                {log.totals[r.key].toFixed(2)}
              </text>
            </g>
          );
        })}
        {/* Grand total */}
        <rect x={TOTALS_X} y={GRID_Y + GRID_H + 4} width={TOTALS_W} height={22} className="ds-fill" />
        <text
          x={TOTALS_X + TOTALS_W / 2}
          y={GRID_Y + GRID_H + 19}
          textAnchor="middle"
          className="ds-num"
        >
          {grandTotal.toFixed(2)}
        </text>

        {/* Status polyline */}
        {linePoints && <polyline points={linePoints} className="ds-line" />}

        {/* Remarks band */}
        <g transform={`translate(0, ${GRID_Y + GRID_H + 14})`}>
          <text x={40} y={16} className="ds-h">Remarks:</text>
          <line x1={GRID_X} y1={20} x2={GRID_X + GRID_W} y2={20} className="ds-rule" />
          {/* Hour ticks under remarks for reference */}
          {Array.from({ length: 25 }).map((_, h) => {
            const x = GRID_X + (h / 24) * GRID_W;
            return <line key={`rh-${h}`} x1={x} y1={14} x2={x} y2={26} className="ds-tick" />;
          })}
          {log.remarks.map((r, i) => {
            const x = xForMin(r.time_min);
            const yOff = 36 + (i % 3) * 12;
            return (
              <g key={`rem-${i}`}>
                <line x1={x} y1={20} x2={x} y2={28} className="ds-tick" />
                <text x={x + 3} y={yOff} className="ds-rem">
                  {r.text}
                </text>
              </g>
            );
          })}
        </g>

        {/* Recap boxes */}
        <g transform={`translate(40, ${VB_H - 175})`}>
          <text x={0} y={0} className="ds-h">Recap — Complete at end of day:</text>

          <text x={0} y={20} className="ds-row">70 hr / 8 day</text>
          <RecapBox x={0} y={28} A={r708.A} B={r708.B} C={r708.C} maxLabel="70" />

          <text x={465} y={20} className="ds-row">60 hr / 7 day</text>
          <RecapBox x={465} y={28} A={r607.A} B={r607.B} C={r607.C} maxLabel="60" />

          <g transform="translate(925, 20)">
            <rect x={0} y={8} width={130} height={108} className="ds-box" />
            <text x={65} y={26} textAnchor="middle" className="ds-row">*34-hour restart</text>
            <text x={65} y={50} textAnchor="middle" className="ds-sub">
              <tspan x={65} dy={0}>If you took 34</tspan>
              <tspan x={65} dy={12}>consecutive hours</tspan>
              <tspan x={65} dy={12}>off duty, you have</tspan>
              <tspan x={65} dy={12}>60/70 hours</tspan>
              <tspan x={65} dy={12}>available.</tspan>
            </text>
          </g>
        </g>
      </svg>
    </div>
  );
}

function RecapBox({
  x, y, A, B, C, maxLabel,
}: { x: number; y: number; A: number; B: number; C: number; maxLabel: string }) {
  const cells: { lbl: string; sub: string[]; val: number }[] = [
    { lbl: "A.", sub: ["On-duty hours today", "(lines 3 + 4)"], val: A },
    { lbl: "B.", sub: [`Hours available —`, `${maxLabel} hr minus A`], val: B },
    { lbl: "C.", sub: ["Total hours", "on duty"], val: C },
  ];
  const CELL_W = 140;
  const CELL_H = 108;
  const GAP = 8;
  return (
    <g transform={`translate(${x}, ${y})`}>
      {cells.map((c, i) => (
        <g key={c.lbl} transform={`translate(${i * (CELL_W + GAP)}, 0)`}>
          <rect x={0} y={8} width={CELL_W} height={CELL_H} className="ds-box" />
          <text x={6} y={26} className="ds-row">{c.lbl}</text>
          <text x={CELL_W / 2} y={62} textAnchor="middle" className="ds-num" style={{ fontSize: 16 }}>
            {c.val.toFixed(2)}
          </text>
          <text x={CELL_W / 2} y={88} textAnchor="middle" className="ds-sub">
            <tspan x={CELL_W / 2} dy={0}>{c.sub[0]}</tspan>
            <tspan x={CELL_W / 2} dy={12}>{c.sub[1]}</tspan>
          </text>
        </g>
      ))}
    </g>
  );
}
