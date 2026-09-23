import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <h2 className="text-xl font-semibold">Страница не найдена</h2>
      <p className="text-sm text-muted-foreground">
        Такого экрана в дашборде нет.
      </p>
      <Link to="/crypto" className="text-sm text-primary underline">
        Вернуться на главную
      </Link>
    </div>
  );
}
