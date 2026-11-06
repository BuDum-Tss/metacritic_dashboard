# Frontend

Веб-интерфейс сервиса: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query. Подробности — в [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Запуск

```bash
npm install
npm run dev      # http://localhost:5173, запросы /api проксируются на http://localhost:8000
npm run build    # проверка типов и сборка в dist/
```

Бэкенд должен быть запущен отдельно (см. `backend/`).
