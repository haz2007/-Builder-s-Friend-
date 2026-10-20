/** Контакты и факты о магазине — меняются в одном месте. */
export const PHONES = [
  { display: "+7 964 705-68-20", href: "tel:+79647056820" },
  { display: "+7 901 768-03-67", href: "tel:+79017680367" },
];

export const YEARS_ON_MARKET = 30;

export const STORE_NAME = "Друг Строителя";

/**
 * Оператор персональных данных для политики конфиденциальности:
 * «ИП Фамилия Имя Отчество, ИНН 000000000000». Заполнить перед запуском —
 * пока пусто, в политике указан магазин и его контакты.
 */
export const LEGAL_OPERATOR: string | null = null;

export const TELEGRAM_BOT_URL = "https://t.me/builders_friend_bot";

export const WORKING_HOURS = "Ежедневно с 9:00 до 19:00";

/**
 * Адрес склада и точка на карте. Пока null — блок «Как нас найти» скрыт.
 * Координаты: в Яндекс.Картах нажать на точку → скопировать «широта, долгота».
 */
export const STORE_LOCATION: {
  address: string;
  latitude: number;
  longitude: number;
  /** Карточка организации в Яндекс.Картах: отзывы, фото, маршрут */
  yandexUrl: string;
} | null = {
  address: "Московская обл., г. о. Химки, д. Чёрная Грязь, Больничный тупик",
  latitude: 55.976238,
  longitude: 37.307756,
  yandexUrl: "https://yandex.ru/maps/org/106138142209/",
};

/** Сразу открывает отзывы в Яндекс.Картах с блоком «Оцените это место» */
export const YANDEX_REVIEW_URL =
  "https://yandex.ru/maps/org/106138142209/reviews/?add-review=true";
