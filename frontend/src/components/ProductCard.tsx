import { Heart, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import QuantityInput from "./QuantityInput";
import { formatPrice } from "../shop/format";
import { stockLabel } from "../shop/stock";
import { useShop } from "../shop/ShopContext";
import type { Product } from "../shop/types";
import VariantPicker from "./VariantPicker";
import { showFallbackImage, sizedImage } from "../shop/images";

export default function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const {
    cart,
    favorites,
    toggleFavorite,
    getSelectedVariant,
    selectVariant,
    changeQuantity,
    canAddVariant,
    maxAddable,
  } = useShop();

  const variant = getSelectedVariant(product);
  const price = variant?.price ?? product.price;
  const unit = variant?.unit ?? product.unit;
  const inStock = (variant?.stockQuantity ?? 0) > 0;
  const inCart = variant ? cart[variant.id] || 0 : 0;
  const canAdd = variant ? canAddVariant(product, variant) : false;
  const isFavorite = favorites.includes(product.id);
  const productUrl = `/product/${product.id}`;

  return (
    <article className="product-card">
      <div className="product-image-wrap">
        <Link to={productUrl} tabIndex={-1} aria-hidden="true">
          <img
            className="product-image"
            src={sizedImage(product.image, 600)}
            onError={showFallbackImage}
            alt={product.name}
            // Первый ряд виден сразу — грузим без задержки, остальное лениво
            loading={priority ? "eager" : "lazy"}
            fetchPriority={priority ? "high" : "auto"}
          />
        </Link>

        {product.badge && <span className="product-badge">{product.badge}</span>}

        <button
          className={`favorite-button ${isFavorite ? "is-favorite" : ""}`}
          aria-label={isFavorite ? "Убрать из избранного" : "Добавить в избранное"}
          onClick={() => toggleFavorite(product.id)}
        >
          <Heart size={18} fill={isFavorite ? "currentColor" : "none"} />
        </button>
      </div>

      <div className="product-info">
        <span className="product-category">{product.category}</span>
        <h3>
          <Link to={productUrl} className="product-title-link">
            {product.name}
          </Link>
        </h3>
        <p>{product.description}</p>

        <VariantPicker
          product={product}
          selected={variant}
          onSelect={(variantId) => selectVariant(product.id, variantId)}
        />

        {product.piecesPerCube !== null && (
          <p className="variant-hint">В 1 м³ — {product.piecesPerCube} шт</p>
        )}

        <div className={`product-stock ${inStock ? "is-available" : "is-unavailable"}`}>
          <span className="product-stock-dot" />
          {stockLabel(product, variant)}
        </div>

        <div className="product-bottom">
          <div className="product-price">
            <strong>{formatPrice(price)}</strong>
            <small>/ {unit}</small>
          </div>

          {variant && inCart ? (
            <QuantityInput
              value={inCart}
              max={inCart + maxAddable(product, variant)}
              onChange={(next) => changeQuantity(variant.id, next - inCart)}
              allowRemove
            />
          ) : (
            <button
              className="add-button"
              onClick={() => variant && changeQuantity(variant.id, 1)}
              disabled={!canAdd}
              aria-label={`Добавить ${product.name} в корзину`}
            >
              <Plus size={19} />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
