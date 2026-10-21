import { useEffect } from "react";

const STORE = "Друг Строителя";

/** Заголовок вкладки при переходах внутри сайта (первую загрузку делает сервер). */
export function usePageTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} | ${STORE}` : `${STORE} — доска, брус и крепёж в Химках`;
  }, [title]);
}
