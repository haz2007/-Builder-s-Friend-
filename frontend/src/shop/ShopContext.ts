import { createContext, useContext } from "react";

import type { ShopContextValue } from "./types";

export const ShopContext = createContext<ShopContextValue | null>(null);

export function useShop(): ShopContextValue {
  const value = useContext(ShopContext);

  if (!value) {
    throw new Error("useShop должен использоваться внутри ShopContext");
  }

  return value;
}
