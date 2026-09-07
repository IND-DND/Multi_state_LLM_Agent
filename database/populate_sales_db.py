import random
from datetime import date, timedelta
from pathlib import Path
import sqlite3

base_dir = Path(__file__).resolve().parent
db_file = base_dir / "sales.db"

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Clear existing data
for table in ["Sales", "Orders", "Products", "Customers", "Employees", "Regions", "Categories", "Suppliers"]:
    cursor.execute(f"DELETE FROM {table}")

# Regions
regions = [
    "North", "South", "East", "West", "Central", "Northeast", "Northwest", "Southeast", "Southwest",
    "Midwest", "Coastal", "Inland", "Pacific", "Mountain", "Plains", "Capital", "Metro", "Suburban",
    "Rural", "International"
]
for name in regions:
    cursor.execute("INSERT INTO Regions(region_name) VALUES (?)", (name,))

# Categories
categories = [
    "Electronics", "Home", "Garden", "Sports", "Clothing", "Toys", "Automotive", "Beauty", "Health",
    "Books", "Music", "Office", "Kitchen", "Pet", "Baby", "Jewelry", "Outdoor", "Tools", "Games", "Food"
]
for name in categories:
    cursor.execute("INSERT INTO Categories(category_name) VALUES (?)", (name,))

# Suppliers
suppliers = [f"Supplier {i}" for i in range(1, 21)]
for name in suppliers:
    cursor.execute("INSERT INTO Suppliers(supplier_name) VALUES (?)", (name,))

# Customers
for i in range(1, 21):
    name = f"Customer {i}"
    email = f"customer{i}@example.com"
    region_id = random.randint(1, 20)
    cursor.execute("INSERT INTO Customers(customer_name, email, region_id) VALUES (?, ?, ?)", (name, email, region_id))

# Employees
for i in range(1, 21):
    name = f"Employee {i}"
    region_id = random.randint(1, 20)
    cursor.execute("INSERT INTO Employees(employee_name, region_id) VALUES (?, ?)", (name, region_id))

# Products
for i in range(1, 21):
    name = f"Product {i}"
    category_id = random.randint(1, 20)
    supplier_id = random.randint(1, 20)
    price = round(random.uniform(10.0, 250.0), 2)
    cursor.execute("INSERT INTO Products(product_name, category_id, supplier_id, price) VALUES (?, ?, ?, ?)", (name, category_id, supplier_id, price))

# Orders
start_date = date(2026, 1, 1)
for i in range(1, 21):
    customer_id = random.randint(1, 20)
    employee_id = random.randint(1, 20)
    order_date = start_date + timedelta(days=i * 2)
    cursor.execute("INSERT INTO Orders(customer_id, employee_id, order_date) VALUES (?, ?, ?)", (customer_id, employee_id, order_date.isoformat()))

# Sales
cursor.execute("SELECT product_id, price FROM Products")
product_prices = {row[0]: row[1] for row in cursor.fetchall()}
for i in range(1, 21):
    order_id = random.randint(1, 20)
    product_id = random.randint(1, 20)
    quantity = random.randint(1, 10)
    total_amount = round(product_prices[product_id] * quantity, 2)
    cursor.execute("INSERT INTO Sales(order_id, product_id, quantity, total_amount) VALUES (?, ?, ?, ?)", (order_id, product_id, quantity, total_amount))

conn.commit()

for table in ["Regions", "Categories", "Suppliers", "Customers", "Employees", "Products", "Orders", "Sales"]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"{table}: {cursor.fetchone()[0]} rows")

conn.close()
