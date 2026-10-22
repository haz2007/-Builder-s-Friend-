import { ArrowRight, Box, ClipboardCheck, Phone, Ruler, Send, Truck, Warehouse } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import CountUp from "../components/CountUp";
import ProductCard from "../components/ProductCard";
import Reveal from "../components/Reveal";
import StoreMap from "../components/StoreMap";
import {
  categoryWithChildrenIds,
  childCategories,
  topLevelCategories,
} from "../shop/categories";
import { showFallbackImage } from "../shop/images";
import { CLOSE_HOUR, OPEN_HOUR, PHONES, STORE_LOCATION, TELEGRAM_BOT_URL, YEARS_ON_MARKET } from "../shop/contacts";
import { storeStatus } from "../shop/hours";
import { pluralize } from "../shop/format";
import { useShop } from "../shop/ShopContext";
import { usePageTitle } from "../shop/usePageTitle";

const STORY_PHOTO = "/photos/story.webp";
const DELIVERY_PHOTO = "/photos/delivery.webp";

const STEPS = [
  {
    icon: Ruler,
    title: "Выберите размер",
    text: "Доска, брус, вагонка — у каждой позиции указаны размеры и остаток на складе.",
  },
  {
    icon: ClipboardCheck,
    title: "Оформите заказ",
    text: "На сайте или по телефону. Подтвердим наличие и созвонимся, чтобы всё уточнить.",
  },
  {
    icon: Truck,
    title: "Доставка или самовывоз",
    text: "Привезём своим транспортом или заберёте сами — на своей или нанятой машине.",
  },
];

export default function HomePage() {
  usePageTitle(null);
  const { products, categories, cartCount, openCheckout } = useShop();
  const navigate = useNavigate();
  const hours = storeStatus();

  const categoryTiles = topLevelCategories(categories).map((category) => {
    const ids = categoryWithChildrenIds(categories, category.id);
    const items = products.filter((product) =>
      product.categoryIds.some((id) => ids.includes(id)),
    );
    const subcategories = childCategories(categories, category.id)
      .map((item) => item.name)
      .join(" · ");
    return { category, count: items.length, image: items[0]?.image, subcategories };
  });
  const popular = products.slice(0, 4);

  function startOrder() {
    if (cartCount > 0) openCheckout();
    else navigate("/catalog");
  }

  return (
    <>
      <section className="home-hero">
        <div className="home-hero-photo" />
        <div className="home-hero-shade" />

        <div className="container home-hero-inner">
          <div className="home-hero-copy">
            <span className="home-eyebrow">
              Семейный магазин пиломатериалов · {YEARS_ON_MARKET} лет опыта
            </span>
            <h1>
              Доска и брус <span>поштучно и кубами</span>
            </h1>
            <p>
              Обрезная доска, брус, вагонка, крепёж и листовые материалы.
              Привезём на объект или отгрузим на вашу машину.
            </p>

            <div className="home-hero-actions">
              <Link to="/catalog" className="home-button home-button-primary">
                Смотреть каталог <ArrowRight size={18} />
              </Link>
              <Link to="/#how" className="home-button home-button-ghost">
                Как мы продаём
              </Link>
            </div>

            <ul className="home-hero-facts">
              <li>
                <strong>
                  <CountUp value={YEARS_ON_MARKET} /> лет
                </strong>
                <span>опыта в пиломатериалах</span>
              </li>
              <li>
                <strong>{products.length ? <CountUp value={products.length} /> : "—"}</strong>
                <span>позиций в наличии</span>
              </li>
              <li>
                <strong>
                  {OPEN_HOUR}:00–{CLOSE_HOUR}:00
                </strong>
                <span className={`home-hours-status ${hours.open ? "is-open" : ""}`}>
                  {hours.text}
                </span>
              </li>
              <li>
                <strong>Любая</strong>
                <span>доставка или самовывоз</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section className="home-section" id="catalog">
        <div className="container">
          <Reveal className="home-heading">
            <div>
              <span className="home-eyebrow">Каталог</span>
              <h2>Что ищете?</h2>
            </div>
            <Link to="/catalog" className="home-link">
              Весь каталог <ArrowRight size={17} />
            </Link>
          </Reveal>

          <div className="category-grid">
            {categoryTiles.map(({ category, count, image, subcategories }, index) => (
              <Reveal key={category.id} delay={index * 90}>
              <Link to={`/catalog/${category.id}`} className="category-tile">
                {image && <img src={image} alt="" loading="lazy" onError={showFallbackImage} />}
                <span className="category-tile-shade" />
                <span className="category-tile-copy">
                  <strong>{category.name}</strong>
                  <small>
                    {count} {pluralize(count, ["товар", "товара", "товаров"])}
                  </small>
                  {subcategories && <em>{subcategories}</em>}
                </span>
                <ArrowRight size={20} className="category-tile-arrow" />
              </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="home-section home-steps-section" id="how">
        <div className="container">
          <Reveal className="home-heading">
            <div>
              <span className="home-eyebrow">Как мы продаём</span>
              <h2>Три шага до материала на объекте</h2>
            </div>
          </Reveal>

          <Reveal>
          <ol className="home-steps">
            {STEPS.map(({ icon: Icon, title, text }, index) => (
              <li key={title} className="reveal-step" style={{ animationDelay: `${index * 120}ms` }}>
                <span className="home-step-number">0{index + 1}</span>
                <Icon size={26} strokeWidth={1.7} />
                <h3>{title}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
          </Reveal>
        </div>
      </section>

      {popular.length > 0 && (
        <section className="home-section">
          <div className="container">
            <Reveal className="home-heading">
              <div>
                <span className="home-eyebrow">Популярное</span>
                <h2>Часто берут</h2>
              </div>
              <Link to="/catalog?sort=popular" className="home-link">
                Все товары <ArrowRight size={17} />
              </Link>
            </Reveal>
            <div className="product-grid">
              {popular.map((product, index) => (
                <Reveal key={product.id} delay={index * 80}>
                  <ProductCard product={product} />
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="home-section home-story" id="about">
        <Reveal className="container home-story-inner">
          <img src={STORY_PHOTO} alt="Склад досок и бруса" loading="lazy" onError={showFallbackImage} />
          <div>
            <span className="home-eyebrow">О магазине</span>
            <h2>С досок всё начиналось</h2>
            <p>
              «Друг Строителя» — семейное дело: наша семья работает с пиломатериалами уже {YEARS_ON_MARKET} лет.
              Начинали с обрезной доски и бруса, потом добавили крепёж, вагонку и листовые материалы —
              всё, за чем строители приезжали к нам и спрашивали «а это есть?».
            </p>
            <p>
              Доставку делаем сами: тот, кто привезёт заказ, знает материал и
              поможет выгрузить. Удобнее забрать самим — отгрузим на вашу
              машину. Цены и остатки на сайте — те же, что на складе.
            </p>
            <div className="home-story-badges">
              <span><Box size={16} /> Доска · брус · вагонка</span>
              <span><Truck size={16} /> Своя доставка</span>
              <span><Warehouse size={16} /> Самовывоз</span>
            </div>
          </div>
        </Reveal>
      </section>

      <section className="home-section" id="delivery">
        <Reveal className="container home-cta">
          <div className="home-cta-copy">
            <span className="home-eyebrow">Доставка и самовывоз</span>
            <h2>Привезём — или заберёте сами</h2>
            <p>
              Соберите заказ на сайте и выберите способ получения. Доставка —
              нашим транспортом прямо на объект, стоимость обсудим по телефону.
              Самовывоз — на своей или нанятой машине: подготовим заказ и
              поможем с погрузкой.
            </p>
            <ul className="home-delivery-list">
              <li><Truck size={18} /> Доставка своим транспортом</li>
              <li><Warehouse size={18} /> Самовывоз со склада</li>
            </ul>
            <button type="button" className="home-button home-button-primary" onClick={startOrder}>
              {cartCount > 0 ? "Оформить заказ" : "Выбрать материалы"} <ArrowRight size={18} />
            </button>
          </div>
          <img src={DELIVERY_PHOTO} alt="Выгрузка пиломатериалов с прицепа" loading="lazy" onError={showFallbackImage} />
        </Reveal>
      </section>

      {STORE_LOCATION && (
        <section className="home-section" id="map">
          <Reveal className="container">
            <StoreMap />
          </Reveal>
        </section>
      )}

      <section className="home-section home-contacts" id="contacts">
        <div className="container home-contacts-inner">
          <div>
            <span className="home-eyebrow">Есть вопросы?</span>
            <h2>Поможем посчитать материал</h2>
            <p>Позвоните или напишите в Telegram — подскажем размеры и объём.</p>
          </div>
          <div className="home-contacts-actions">
            {PHONES.map((phone) => (
              <a key={phone.href} className="home-button home-button-light" href={phone.href}>
                <Phone size={18} /> {phone.display}
              </a>
            ))}
            <a
              className="home-button home-button-outline"
              href={TELEGRAM_BOT_URL}
              target="_blank"
              rel="noreferrer"
            >
              <Send size={18} /> Написать в Telegram
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
