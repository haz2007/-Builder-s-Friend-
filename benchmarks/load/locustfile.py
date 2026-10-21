"""Покупатели листают магазин: главная, каталог, поиск, карточки товаров.

Только чтение — так ведёт себя почти весь трафик магазина. Заказы и
регистрация упираются в лимиты частоты с одного IP, их здесь не меряем.
"""

import random

from locust import HttpUser, between, task

SEARCHES = ["доска", "брус 100х100", "вагонка", "саморезы", "досака", "фанера"]


class Shopper(HttpUser):
    # Человек думает между кликами 1–4 секунды
    wait_time = between(1, 4)

    def on_start(self):
        products = self.client.get("/api/v1/products/?limit=100", name="/api/v1/products/").json()
        self.product_ids = [product["id"] for product in products] or [1]

    @task(3)
    def home(self):
        self.client.get("/", name="/ (страница + SEO head)")
        self.client.get("/api/v1/products/?limit=100", name="/api/v1/products/")
        self.client.get("/api/v1/categories/", name="/api/v1/categories/")

    @task(4)
    def product(self):
        product_id = random.choice(self.product_ids)
        self.client.get(f"/product/{product_id}", name="/product/{id} (SEO head)")
        self.client.get(f"/api/v1/products/{product_id}", name="/api/v1/products/{id}")

    @task(2)
    def search(self):
        query = random.choice(SEARCHES)
        self.client.get("/api/v1/products/", params={"search": query}, name="/api/v1/products/?search")
        self.client.get("/api/v1/products/suggest", params={"q": query}, name="/api/v1/products/suggest")

    @task(1)
    def catalog_page(self):
        self.client.get("/catalog", name="/catalog (SEO head)")
