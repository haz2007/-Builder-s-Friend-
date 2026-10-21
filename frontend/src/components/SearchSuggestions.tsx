import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getProductSuggestions } from "../api";

/** «Возможно, вы искали»: когда по словам ничего нет — похожие названия с сервера. */
export default function SearchSuggestions({ query }: { query: string }) {
  const [found, setFound] = useState<{ query: string; items: { id: number; name: string }[] }>({
    query: "",
    items: [],
  });
  const phrase = query.trim();

  useEffect(() => {
    if (phrase.length < 2) return;
    const controller = new AbortController();
    // Ждём, пока покупатель допечатает
    const timer = window.setTimeout(() => {
      getProductSuggestions(phrase, controller.signal)
        .then((items) => setFound({ query: phrase, items }))
        .catch(() => undefined);
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [phrase]);

  if (found.query !== phrase || found.items.length === 0) return null;

  return (
    <div className="search-suggestions">
      <span>Возможно, вы искали:</span>
      {found.items.map((item) => (
        <Link key={item.id} to={`/product/${item.id}`}>
          {item.name}
        </Link>
      ))}
    </div>
  );
}
