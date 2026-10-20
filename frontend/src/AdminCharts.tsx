import { useState } from "react";

import type { AdminAnalytics } from "./api";

const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

function parseDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatMoney(value: number) {
  return `${Math.round(value).toLocaleString("ru-RU")} ₽`;
}

function compactMoney(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} млн`;
  if (value >= 1_000) return `${Math.round(value / 1_000)} тыс`;
  return String(Math.round(value));
}

function bucketLabel(start: string, end: string, granularity: AdminAnalytics["granularity"]) {
  const from = parseDate(start);
  const to = parseDate(end);
  if (granularity === "day") return `${from.getDate()} ${MONTHS[from.getMonth()]}`;
  if (granularity === "month") return `${MONTHS[from.getMonth()]} ${from.getFullYear()}`;
  return from.getMonth() === to.getMonth()
    ? `${from.getDate()}–${to.getDate()} ${MONTHS[to.getMonth()]}`
    : `${from.getDate()} ${MONTHS[from.getMonth()]} – ${to.getDate()} ${MONTHS[to.getMonth()]}`;
}

/** Чистый «потолок» шкалы: 0 / половина / максимум круглыми числами. */
function niceMax(value: number) {
  if (value <= 0) return 1000;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((multiplier) => multiplier * power >= value) ?? 10;
  return step * power;
}

/** Столбик со скруглённым верхом и прямым основанием. */
function columnPath(x: number, y: number, width: number, height: number) {
  const r = Math.min(4, width / 2, height);
  return `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
}

const PERIOD_NAMES = { day: "по дням", week: "по неделям", month: "по месяцам" };

export function RevenueChart({ analytics }: { analytics: AdminAnalytics }) {
  const [active, setActive] = useState<number | null>(null);
  const series = analytics.revenue_series;
  const total = series.reduce((sum, bucket) => sum + bucket.revenue, 0);

  if (series.length === 0) {
    return <p className="admin-empty">За выбранный период заказов нет.</p>;
  }

  const width = 640;
  const height = 220;
  const padding = { top: 22, right: 8, bottom: 26, left: 52 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const max = niceMax(Math.max(...series.map((bucket) => bucket.revenue)));
  const band = plotWidth / series.length;
  const columnWidth = Math.min(24, band * 0.6);
  const peak = series.reduce((best, bucket, index) => (bucket.revenue > series[best].revenue ? index : best), 0);
  // Подписи по оси X — не больше ~7, чтобы не наезжали
  const labelEvery = Math.ceil(series.length / 7);
  const activeBucket = active !== null ? series[active] : null;

  return (
    <div className="revenue-chart">
      <div className="revenue-chart-total">
        <strong>{formatMoney(total)}</strong>
        <span>выручка без отмен, {PERIOD_NAMES[analytics.granularity]}</span>
      </div>

      <div className="revenue-chart-plot">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Выручка ${PERIOD_NAMES[analytics.granularity]}`}>
          {[0, 0.5, 1].map((share) => {
            const y = padding.top + plotHeight * (1 - share);
            return (
              <g key={share}>
                <line className="chart-grid" x1={padding.left} x2={width - padding.right} y1={y} y2={y} />
                <text className="chart-tick" x={padding.left - 8} y={y + 4} textAnchor="end">
                  {compactMoney(max * share)}
                </text>
              </g>
            );
          })}

          {series.map((bucket, index) => {
            const columnHeight = (bucket.revenue / max) * plotHeight;
            const x = padding.left + band * index + (band - columnWidth) / 2;
            const y = padding.top + plotHeight - columnHeight;
            const label = bucketLabel(bucket.start, bucket.end, analytics.granularity);
            return (
              <g key={bucket.start}>
                {columnHeight > 0 && (
                  <path
                    className={`chart-column ${active === index ? "is-active" : ""}`}
                    d={columnPath(x, y, columnWidth, columnHeight)}
                  />
                )}
                {index === peak && bucket.revenue > 0 && (
                  <text className="chart-value" x={x + columnWidth / 2} y={y - 6} textAnchor="middle">
                    {compactMoney(bucket.revenue)}
                  </text>
                )}
                {index % labelEvery === 0 && (
                  <text className="chart-tick" x={padding.left + band * index + band / 2} y={height - 6} textAnchor="middle">
                    {label}
                  </text>
                )}
                {/* Зона наведения — вся полоса, а не только столбик */}
                <rect
                  className="chart-hit"
                  x={padding.left + band * index}
                  y={padding.top}
                  width={band}
                  height={plotHeight}
                  tabIndex={0}
                  aria-label={`${label}: ${formatMoney(bucket.revenue)}, заказов ${bucket.orders}`}
                  onPointerEnter={() => setActive(index)}
                  onPointerLeave={() => setActive(null)}
                  onFocus={() => setActive(index)}
                  onBlur={() => setActive(null)}
                />
              </g>
            );
          })}
        </svg>

        {activeBucket && active !== null && (
          <div
            className="chart-tooltip"
            style={{ left: `${((padding.left + band * active + band / 2) / width) * 100}%` }}
          >
            <strong>{formatMoney(activeBucket.revenue)}</strong>
            <span>{bucketLabel(activeBucket.start, activeBucket.end, analytics.granularity)}</span>
            <span>Заказов: {activeBucket.orders}</span>
          </div>
        )}
      </div>

      <details className="chart-table">
        <summary>Показать таблицей</summary>
        <table>
          <thead>
            <tr><th>Период</th><th>Заказов</th><th>Выручка</th></tr>
          </thead>
          <tbody>
            {series.map((bucket) => (
              <tr key={bucket.start}>
                <td>{bucketLabel(bucket.start, bucket.end, analytics.granularity)}</td>
                <td>{bucket.orders}</td>
                <td>{formatMoney(bucket.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

const PIPELINE_LABELS: Record<string, string> = {
  NEW: "Новые — ждут подтверждения",
  CONFIRMED: "Подтверждены",
  PREPARING: "Готовятся",
  READY_FOR_DELIVERY: "Готовы к выдаче",
  ON_THE_WAY: "В пути",
};

export function PipelinePanel({
  analytics,
  onSelect,
}: {
  analytics: AdminAnalytics;
  onSelect: (status: string) => void;
}) {
  const total = analytics.pipeline.reduce((sum, row) => sum + row.count, 0);
  const max = Math.max(1, ...analytics.pipeline.map((row) => row.count));

  return (
    <div className="pipeline">
      <div className="revenue-chart-total">
        <strong>{total}</strong>
        <span>заказов в работе прямо сейчас</span>
      </div>
      {analytics.pipeline.map((row) => (
        <button
          key={row.status}
          type="button"
          className={`pipeline-row ${row.count === 0 ? "is-empty" : ""}`}
          onClick={() => onSelect(row.status)}
          title="Открыть эти заказы"
        >
          <span className="pipeline-label">{PIPELINE_LABELS[row.status] ?? row.status}</span>
          <span className="pipeline-track">
            {row.count > 0 && (
              <span className="pipeline-fill" style={{ width: `${(row.count / max) * 100}%` }} />
            )}
          </span>
          <strong className="pipeline-count">{row.count}</strong>
        </button>
      ))}
    </div>
  );
}

export function CategoryRevenue({ analytics }: { analytics: AdminAnalytics }) {
  const rows = analytics.category_revenue;
  const total = rows.reduce((sum, row) => sum + row.revenue, 0);
  const max = Math.max(1, ...rows.map((row) => row.revenue));

  if (rows.length === 0) {
    return <p className="admin-empty">Нет продаж за выбранный период.</p>;
  }

  return (
    <div className="category-revenue">
      {rows.map((row) => (
        <div className="category-revenue-row" key={row.name}>
          <span className="pipeline-label">{row.name}</span>
          <span className="pipeline-track">
            <span className="pipeline-fill" style={{ width: `${(row.revenue / max) * 100}%` }} />
          </span>
          <span className="category-revenue-value">
            <strong>{formatMoney(row.revenue)}</strong>
            <small>{total ? Math.round((row.revenue / total) * 100) : 0}%</small>
          </span>
        </div>
      ))}
    </div>
  );
}
