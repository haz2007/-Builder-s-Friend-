import type { ApiCategory } from "../api";

export type ProductVariant = {
  id: number;
  name: string;
  unit: string;
  price: number;
  /** Сколько базовых единиц товара списывает 1 единица варианта */
  baseQuantity: number;
  /** Сколько единиц варианта можно купить из общего склада */
  stockQuantity: number;
};

export type Product = {
  id: number;
  name: string;
  category: string;
  categoryId: number;
  categoryIds: number[];
  categoryNames: string[];
  /** Для досок с размерами: сколько целых штук в 1 м³ */
  piecesPerCube: number | null;
  dimensions: { thickness: number; width: number; length: number } | null;
  description: string;
  price: number;
  unit: string;
  /** Общий остаток в базовой единице (для досок — штуки) */
  stockQuantity: number;
  image: string;
  badge?: string;
  variants: ProductVariant[];
};

export type CartEntry = {
  product: Product;
  variant: ProductVariant;
  quantity: number;
};

export type ShopContextValue = {
  products: Product[];
  categories: ApiCategory[];
  loading: boolean;
  loadError: string;
  cart: Record<number, number>;
  cartCount: number;
  favorites: number[];
  toggleFavorite: (productId: number) => void;
  getSelectedVariant: (product: Product) => ProductVariant | undefined;
  selectVariant: (productId: number, variantId: number) => void;
  changeQuantity: (variantId: number, amount: number) => void;
  canAddVariant: (product: Product, variant: ProductVariant) => boolean;
  /** Сколько единиц варианта ещё можно положить в корзину */
  maxAddable: (product: Product, variant: ProductVariant) => number;
  openCart: () => void;
  openCheckout: () => void;
  /** Окно «Заказать по телефону»: товар под заказ или «не нашли нужное» */
  openCallUs: (options?: { product?: string; callback?: boolean }) => void;
};
