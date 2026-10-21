import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
// Шрифты — со своего сервера: быстрее, чем Google Fonts из России,
// и адрес посетителя не уходит третьей стороне (152-ФЗ)
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/manrope/800.css";
import "./index.css";
import App from "./App.tsx";
// Админка — отдельным файлом: покупателям не нужно скачивать её код и стили
// Точка входа, а не модуль компонентов: Fast Refresh здесь не нужен
// oxlint-disable-next-line react/only-export-components
const Admin = lazy(() => import("./Admin.tsx"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route
          path="/admin/*"
          element={
            <Suspense fallback={null}>
              <Admin />
            </Suspense>
          }
        />
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
