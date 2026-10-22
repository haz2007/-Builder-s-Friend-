import { Link } from "react-router-dom";

import type { CookieChoice } from "../shop/metrika";

/**
 * Баннер cookie: Метрика запускается только после «Принять».
 * raised — когда внизу видна панель корзины, баннер поднимается над ней.
 */
export default function CookieBanner({
  onChoose,
  raised,
}: {
  onChoose: (choice: CookieChoice) => void;
  raised: boolean;
}) {
  return (
    <div
      className={raised ? "cookie-banner cookie-banner-raised" : "cookie-banner"}
      role="dialog"
      aria-label="Файлы cookie"
    >
      <p>
        Мы хотим использовать файлы cookie и Яндекс Метрику, чтобы понимать, какие
        товары смотрят и где сайт неудобен. Без вашего согласия статистика не
        собирается — сайт работает так же.{" "}
        <Link to="/privacy">Подробнее</Link>
      </p>
      <div className="cookie-banner-actions">
        <button type="button" className="button button-dark" onClick={() => onChoose("accepted")}>
          Принять
        </button>
        <button type="button" className="button button-light" onClick={() => onChoose("declined")}>
          Только необходимые
        </button>
      </div>
    </div>
  );
}
