CREATE TABLE Customers(
customer_id INTEGER PRIMARY KEY,
customer_name TEXT,
email TEXT,
region_id INTEGER
);

CREATE TABLE Products(
product_id INTEGER PRIMARY KEY,
product_name TEXT,
category_id INTEGER,
supplier_id INTEGER,
price REAL
);
CREATE TABLE Orders(
order_id INTEGER PRIMARY KEY,
customer_id INTEGER,
employee_id INTEGER,
order_date TEXT
);
CREATE TABLE Sales(
sale_id INTEGER PRIMARY KEY,
order_id INTEGER,
product_id INTEGER,
quantity INTEGER,
total_amount REAL
);
CREATE TABLE Employees(
employee_id INTEGER PRIMARY KEY,
employee_name TEXT,
region_id INTEGER
);
CREATE TABLE Regions(
region_id INTEGER PRIMARY KEY,
region_name TEXT
);
CREATE TABLE Categories(
category_id INTEGER PRIMARY KEY,
category_name TEXT
);
CREATE TABLE Suppliers(
supplier_id INTEGER PRIMARY KEY,
supplier_name TEXT
);
