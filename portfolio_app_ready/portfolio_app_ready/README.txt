# Portfolio AI

## Быстрый старт

### 1. Установи PostgreSQL
https://www.postgresql.org/download/windows/

### 2. Создай базу данных
В pgAdmin выполни:
```sql
CREATE DATABASE portfolio_db;
CREATE USER portfolio_user WITH PASSWORD 'твой_пароль';
GRANT ALL PRIVILEGES ON DATABASE portfolio_db TO portfolio_user;
GRANT ALL ON SCHEMA public TO portfolio_user;
ALTER DATABASE portfolio_db OWNER TO portfolio_user;
```

### 3. Создай .env файл
Скопируй `.env.example` в `.env` и заполни своими данными.

### 4. Запусти проект
```bash
py setup.py
```

Открой http://127.0.0.1:8000