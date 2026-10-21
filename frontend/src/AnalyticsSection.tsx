import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getAdminAnalytics } from "./api";
import type { AdminAnalytics, AdminAnalyticsPeriod } from "./api";
import { CategoryRevenue, PipelinePanel, RevenueChart } from "./AdminCharts";
import AdminReports from "./AdminReports";

/** Обзор: KPI, графики, популярные товары, низкие остатки и SQL-отчёты. */
export default function AnalyticsSection({
  token,
  onSelectStatus,
}: {
  token: string;
  /** Клик по этапу воронки открывает заказы с этим статусом */
  onSelectStatus: (status: string) => void;
}) {
  const navigate = useNavigate();
  const [analyticsPeriod, setAnalyticsPeriod] = useState<AdminAnalyticsPeriod>("30d");
  const [analyticsFrom, setAnalyticsFrom] = useState("");
  const [analyticsTo, setAnalyticsTo] = useState("");
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState("");

  useEffect(() => {
    if (!token) return;
    if (analyticsPeriod === "custom" && (!analyticsFrom || !analyticsTo)) {
      setAnalytics(null);
      setAnalyticsError("Выбери обе даты для произвольного периода.");
      return;
    }
    if (analyticsPeriod === "custom" && analyticsFrom > analyticsTo) {
      setAnalytics(null);
      setAnalyticsError("Дата начала не может быть позже даты окончания.");
      return;
    }
    let cancelled = false;
    setAnalyticsLoading(true);
    setAnalyticsError("");
    getAdminAnalytics(token, analyticsPeriod, analyticsFrom, analyticsTo)
      .then((data) => { if (!cancelled) setAnalytics(data); })
      .catch((err) => {
        if (!cancelled) setAnalyticsError(err instanceof Error ? err.message : "Не удалось загрузить аналитику.");
      })
      .finally(() => { if (!cancelled) setAnalyticsLoading(false); });
    return () => { cancelled = true; };
  }, [token, analyticsPeriod, analyticsFrom, analyticsTo]);

  return (
    <section className="admin-card admin-statistics">
      <div className="admin-section-heading">
        <div>
          <span className="admin-eyebrow">АНАЛИТИКА</span>
          <h2>Статистика магазина</h2>
          <p>Данные рассчитываются на сервере по всем заказам за выбранный период.</p>
        </div>
        {analyticsLoading && <span>Обновляем статистику...</span>}
      </div>
      <div className="admin-analytics-controls">
        <label>Период
          <select value={analyticsPeriod} onChange={(event) => setAnalyticsPeriod(event.target.value as AdminAnalyticsPeriod)}>
            <option value="7d">Последние 7 дней</option>
            <option value="30d">Последние 30 дней</option>
            <option value="90d">Последние 90 дней</option>
            <option value="all">За всё время</option>
            <option value="custom">Выбрать даты</option>
          </select>
        </label>
        {analyticsPeriod === "custom" && <>
          <label>С даты<input type="date" value={analyticsFrom} onChange={(event) => setAnalyticsFrom(event.target.value)} /></label>
          <label>По дату<input type="date" value={analyticsTo} onChange={(event) => setAnalyticsTo(event.target.value)} /></label>
        </>}
      </div>
      {analyticsError && <p className="admin-error">{analyticsError}</p>}
      {analytics && <>
        <div className="admin-stats-grid admin-kpi-grid">
          <article className="admin-stat-card admin-stat-primary"><span>Сумма неотменённых заказов</span><strong>{analytics.revenue.not_cancelled.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</strong><small>Включая ещё не доставленные</small></article>
          <article className="admin-stat-card"><span>Фактическая выручка</span><strong>{analytics.revenue.delivered.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</strong><small>Только доставленные заказы</small></article>
          <article className="admin-stat-card"><span>Всего заказов</span><strong>{analytics.orders.total}</strong><small>Отменено: {analytics.orders.cancelled}</small></article>
          <article className="admin-stat-card"><span>Средний чек</span><strong>{analytics.average_order_value.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</strong><small>Без отменённых заказов</small></article>
          <article className="admin-stat-card"><span>Доставлено</span><strong>{analytics.orders.delivered}</strong><small>Конверсия: {analytics.delivery_conversion_rate.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%</small></article>
        </div>
        <div className="admin-statistics-columns">
          <div className="admin-stat-panel admin-stat-panel-wide">
            <h3>Выручка за период</h3>
            <RevenueChart analytics={analytics} />
          </div>
          <div className="admin-stat-panel">
            <h3>Заказы по этапам</h3>
            <PipelinePanel
              analytics={analytics}
              onSelect={(status) => {
                onSelectStatus(status);
                navigate("/admin/orders");
              }}
            />
          </div>
          <div className="admin-stat-panel">
            <h3>Выручка по разделам</h3>
            <CategoryRevenue analytics={analytics} />
          </div>
          <div className="admin-stat-panel">
            <h3>Популярные товары</h3>
            {analytics.top_products.length === 0 ? <p className="admin-empty">Нет продаж за выбранный период.</p> : <div className="admin-popular-products">
              {analytics.top_products.map((product, index) => <div className="admin-popular-product" key={product.product_id}>
                <span className="admin-popular-rank">{index + 1}</span><div className="admin-popular-product-info"><strong>{product.name}</strong><span>Продано: {product.quantity} · {product.revenue.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽</span></div>
              </div>)}
            </div>}
          </div>
          <div className="admin-stat-panel admin-low-stock-panel">
            <h3>Низкий остаток (10 или меньше)</h3>
            {analytics.low_stock_products.length === 0 ? <p className="admin-empty">Нет товаров с низким остатком.</p> : <div className="admin-low-stock-list">
              {analytics.low_stock_products.map((product) => <div className="admin-low-stock-item" key={product.id}><strong>{product.name}</strong><span>{product.stock_quantity} {product.unit}</span></div>)}
            </div>}
          </div>
        </div>
        <AdminReports token={token} period={analyticsPeriod} dateFrom={analyticsFrom} dateTo={analyticsTo} />
      </>}
    </section>
  );
}
