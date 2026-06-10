import subprocess
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def run(cmd, check=True):
    print(f'\n>>> {cmd}')
    result = subprocess.run(cmd, shell=True, check=check, cwd=BASE_DIR)
    return result

def check_env():
    env_file = BASE_DIR / '.env'

    if not env_file.exists():
        print('\n⚠ Файл .env не найден — создаю автоматически...')
        with open(env_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write('SECRET_KEY=django-insecure-portfolio-ai-secret-key-change-in-production\n')
            f.write('DEBUG=True\n')
            f.write('DB_NAME=portfolio_db\n')
            f.write('DB_USER=portfolio_user\n')
            f.write('DB_PASSWORD=\n')
            f.write('DB_HOST=localhost\n')
            f.write('DB_PORT=5432\n')
        print('Создан .env — открой его и заполни DB_PASSWORD')
        input('Нажми Enter после заполнения...')
    else:
        # Перезаписываем существующий .env в правильной кодировке
        try:
            content = env_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Файл в неправильной кодировке — читаем как latin-1 и перезаписываем
            content = env_file.read_text(encoding='latin-1')
            env_file.write_text(content, encoding='utf-8', newline='\n')
            print('✓ Исправлена кодировка .env файла')

def main():
    print('=' * 50)
    print('  Portfolio AI — Setup')
    print('=' * 50)

    check_env()

    print('\n[1/4] Установка зависимостей...')
    run(f'{sys.executable} -m pip install -r requirements.txt')

    print('\n[2/4] Применение миграций...')
    run(f'{sys.executable} manage.py makemigrations', check=False)
    run(f'{sys.executable} manage.py migrate')

    print('\n[4/4] Запуск сервера...')
    print('      http://127.0.0.1:8000')
    print('      Ctrl+C для остановки\n')
    run(f'{sys.executable} manage.py runserver')

if __name__ == '__main__':
    main()