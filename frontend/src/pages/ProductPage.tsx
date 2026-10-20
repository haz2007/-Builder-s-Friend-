import { ChevronRight, Minus, Package, Plus, ShoppingCart } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import VariantPicker from "../components/VariantPicker";
import { parentCategory } from "../shop/categories";
import { formatPrice, formatQuantity } from "../shop/format";
import { useShop } from "../shop/ShopContext";
import { stockLabel } from "../shop/stock";
import { showFallbackImage } from "../shop/images";

export default function ProductPage() {
  const { productId } = useParams();
  const {
    products,
    categories,
    loading,
    cart,
    getSelectedVariant,
    selectVariant,
    changeQuantity,
    maxAddable,
    openCart,
  } = useShop();
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState("");

  const product = products.find((item) => String(item.id) === productId);

  if (!product) {
    return (
      <section className="page-section">
        <div className="container empty-results">
          <Package size={30} />
          <h3>{loading ? "Загружаем товар" : "Товар не найден"}</h3>
          {!loading && (
            <Link to="/catalog" className="button button-dark">
              В каталог
            </Link>
          )}
        </div>
      </section>
    );
  }

  const variant = getSelectedVariant(product);
  const available = variant ? maxAddable(product, variant) : 0;
  const amount = Math.min(quantity, Math.max(available, 1));
  const inCart = variant ? cart[variant.id] || 0 : 0;
  const category = categories.find((item) => item.id === product.categoryId);
  const parent = category ? parentCategory(categories, category) : undefined;

  function addToCart() {
    if (!variant || available < 1) return;
    changeQuantity(variant.id, amount);
    setAdded(`Добавлено: ${amount} ${variant.unit}`);
    setQuantity(1);
  }

  return (
    <section className="page-section product-page">
      <div className="container">
        <nav className="breadcrumbs" aria-label="Навигация">
          <Link to="/">Главная</Link>
          <ChevronRight size={14} />
          <Link to="/catalog">Каталог</Link>
          {parent && (
            <>
              <ChevronRight size={14} />
              <Link to={`/catalog/${parent.id}`}>{parent.name}</Link>
            </>
          )}
          {category && (
            <>
              <ChevronRight size={14} />
              <Link to={`/catalog/${category.id}`}>{category.name}</Link>
            </>
          )}
          <ChevronRight size={14} />
          <span>{product.name}</span>
        </nav>

        <div className="product-page-grid">
          <div className="product-page-image">
            <img src={product.image} alt={product.name} onError={showFallbackImage} />
          </div>

          <div className="product-page-info">
            <span className="product-category">{product.category}</span>
            <h1>{product.name}</h1>
            <p className="product-page-description">{product.description}</p>

            <VariantPicker
              product={product}
              selected={variant}
              size="large"
              onSelect={(variantId) => {
                selectVariant(product.id, variantId);
                setQuantity(1);
                setAdded("");
              }}
            />

            {variant && (
              <div className="product-page-buy">
                <div className="product-page-price">
                  <strong>{formatPrice(variant.price)}</strong>
                  <span>за 1 {variant.unit}</span>
                </div>

                <div
                  className={`product-stock ${
                    variant.stockQuantity > 0 ? "is-available" : "is-unavailable"
                  }`}
                >
                  <span className="product-stock-dot" />
                  {stockLabel(product, variant)}
                </div>

                {variant.baseQuantity !== 1 && (
                  <p className="product-page-note">
                    1 {variant.unit} = {formatQuantity(variant.baseQuantity)}{" "}
                    {product.unit}. Продаётся только целыми {variant.unit}.
                  </p>
                )}

                <div className="product-page-actions">
                  <div className="quantity-control quantity-control-large">
                    <button
                      onClick={() => setQuantity(Math.max(1, amount - 1))}
                      disabled={amount <= 1}
                      aria-label="Меньше"
                    >
                      <Minus size={16} />
                    </button>
                    <span>{amount}</span>
                    <button
                      onClick={() => setQuantity(amount + 1)}
                      disabled={amount >= available}
                      aria-label="Больше"
                    >
                      <Plus size={16} />
                    </button>
                  </div>

                  <button
                    className="button button-primary"
                    onClick={addToCart}
                    disabled={available < 1}
                  >
                    <ShoppingCart size={18} />
                    {available < 1
                      ? "Больше нет в наличии"
                      : `В корзину · ${formatPrice(variant.price * amount)}`}
                  </button>
                </div>

                {(added || inCart > 0) && (
                  <p className="product-page-added">
                    {added || `В корзине: ${inCart} ${variant.unit}`}{" "}
                    <button type="button" onClick={openCart}>
                      Открыть корзину
                    </button>
                  </p>
                )}
              </div>
            )}

            <dl className="product-specs">
              {product.dimensions && (
                <>
                  <dt>Размеры</dt>
                  <dd>
                    {product.dimensions.thickness} × {product.dimensions.width} ×{" "}
                    {product.dimensions.length} мм
                  </dd>
                </>
              )}
              {product.piecesPerCube !== null && (
                <>
                  <dt>Штук в 1 м³</dt>
                  <dd>{product.piecesPerCube}</dd>
                </>
              )}
              <dt>На складе</dt>
              <dd>
                {formatQuantity(product.stockQuantity)} {product.unit}
              </dd>
              <dt>Категории</dt>
              <dd>{product.categoryNames.join(", ") || product.category}</dd>
            </dl>
          </div>
        </div>
      </div>
    </section>
  );
}
