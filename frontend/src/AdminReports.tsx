import { useEffect, useState } from "react";

import { getAdminReports, type AdminAnalyticsPeriod, type AdminReports as Reports } from "./api";

const money = (value: number) => `${value.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽`;
const monthName = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("ru-RU", { month: "long", year: "numeric" });

const ABC_HINT: Record<string, string> = {
  A: "первые 80 % выручки",
  B: "следующие 15 %",
  C: "остальные 5 %",
};

type Props = {
  token: string;
  period: AdminAnalyticsPeriod;
  dateFrom?: string;
  dateTo?: string;
};

/** ABC-анализ, сводка по месяцам и повторные покупки — считает PostgreSQL. */
export default function AdminReports({ token, period, dateFrom, dateTo }: Props) {
  const [reports, setReports] = useState<Reports | null>(null);

  useEffect(() => {
    if (period === "custom" && (!dateFrom || !dateTo)) return;
    let cancelled = false;
    getAdminReports(token, period, dateFrom, dateTo)
      .then((data) => { if (!cancelled) setReports(data); })
      .catch(() => { if (!cancelled) setReports(null); });
    return () => { cancelled = true; };
  }, [token, period, dateFrom, dateTo]);

  if (!reports) return null;
  const { abc, monthly, customers } = reports;

  return (
    <div className="admin-reports">
      <div className="admin-stat-panel admin-stat-panel-wide">
        <h3>ABC-анализ товаров</h3>
        <p className="admin-panel-note">
          Какие товары приносят основную выручку за период: A — {ABC_HINT.A}, B — {ABC_HINT.B}, C — {ABC_HINT.C}.
        </p>
        {abc.length === 0 ? <p className="admin-empty">Нет продаж за выбранный период.</p> : (
          <div className="admin-table-wrap">
            <table className="admin-table admin-report-table">
              <thead>
                <tr><th>№</th><th>Товар</th><th>Продано</th><th>Выручка</th><th>Доля</th><th>Накопленная</th><th>Класс</th></tr>
              </thead>
              <tbody>
                {abc.map((row) => (
                  <tr key={row.product_id}>
                    <td>{row.rank}</td>
                    <td><strong>{row.name}</strong></td>
                    <td>{row.base_quantity_sold.toLocaleString("ru-RU")} {row.unit}</td>
                    <td>{money(row.revenue)}</td>
                    <td>{row.share_pct.toLocaleString("ru-RU")} %</td>
                    <td>{row.cumulative_pct.toLocaleString("ru-RU")} %</td>
                    <td><span className={`admin-abc admin-abc-${row.abc_class.toLowerCase()}`}>{row.abc_class}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="admin-stats-grid admin-reports-grid">
        <div className="admin-stat-panel">
          <h3>По месяцам</h3>
          {monthly.length === 0 ? <p className="admin-empty">Заказов за последний год нет.</p> : (
            <div className="admin-table-wrap">
              <table className="admin-table admin-report-table">
                <thead>
                  <tr><th>Месяц</th><th>Заказы</th><th>Выручка</th><th>Средний чек</th><th>Самовывоз</th><th>К прошлому</th></tr>
                </thead>
                <tbody>
                  {monthly.map((row) => (
                    <tr key={row.month}>
                      <td>{monthName(row.month)}</td>
                      <td>{row.orders}</td>
                      <td>{money(row.revenue)}</td>
                      <td>{money(row.average_check)}</td>
                      <td>{row.pickup_pct.toLocaleString("ru-RU")} %</td>
                      <td className={row.revenue_change_pct === null ? "" : row.revenue_change_pct >= 0 ? "admin-up" : "admin-down"}>
                        {row.revenue_change_pct === null ? "—" : `${row.revenue_change_pct > 0 ? "+" : ""}${row.revenue_change_pct.toLocaleString("ru-RU")} %`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="admin-stat-panel">
          <h3>Повторные покупки</h3>
          <div className="admin-repeat">
            <div><strong>{customers.customers}</strong><span>покупателей с заказами</span></div>
            <div><strong>{customers.repeat_customers}</strong><span>вернулись за новым заказом</span></div>
            <div>
              <strong>{customers.average_days_between_orders === null ? "—" : customers.average_days_between_orders.toLocaleString("ru-RU")}</strong>
              <span>дней в среднем между заказами</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
