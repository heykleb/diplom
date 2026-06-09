ГОТОВЫЙ ПРОЕКТ: Portfolio Optimizer

Как запустить на Windows:

1. Распакуйте архив.
2. Откройте PowerShell в папке проекта, где лежит manage.py.
3. Установите зависимости:
   pip install -r requirements.txt

   python -m pip install -r requirements.txt

4. Выполните миграции:
python -m pip install yfinance
   python manage.py makemigrations
   py -m pip install scipy
   python manage.py migrate

5. Создайте пользователя:
   python manage.py createsuperuser

6. Запустите сервер:
   python manage.py runserver

7. Откройте сайт:
   http://127.0.0.1:8000/

Если появится страница входа, войдите под логином и паролем суперпользователя.


py -m pip install numpy pandas scipy yfinance

ollama run llama3

py -m pip install ollama

