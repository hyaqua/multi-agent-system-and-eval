-- ============================================================
-- SQL Query Engine – Example Queries
-- ============================================================
-- These queries demonstrate all supported features.
-- Run them in the REPL or use: python main.py --demo
-- ============================================================

-- 1. Load CSV files as tables
LOAD users FROM 'sample_users.csv';
LOAD orders FROM 'sample_orders.csv';

-- 2. SELECT * (all columns)
SELECT * FROM users;

-- 3. SELECT specific columns
SELECT name, age FROM users;

-- 4. WHERE with comparison operators (=, !=, <, >, <=, >=)
SELECT name, age, city FROM users WHERE age > 25;
SELECT name, salary FROM users WHERE city = 'Chicago';
SELECT name, age FROM users WHERE age >= 30;
SELECT name, age FROM users WHERE age <= 28;
SELECT name, city FROM users WHERE city != 'New York';

-- 5. WHERE with AND and OR
SELECT name, age, city FROM users WHERE age >= 30 AND city = 'New York';
SELECT name, city FROM users WHERE city = 'Boston' OR city = 'Chicago';
SELECT name, age, salary FROM users WHERE (age < 30 OR age > 40) AND salary > 60000;

-- 6. ORDER BY (ASC and DESC, multiple columns)
SELECT name, salary FROM users ORDER BY salary DESC;
SELECT name, age, city FROM users ORDER BY city ASC, age DESC;

-- 7. LIMIT
SELECT name, age FROM users ORDER BY age DESC LIMIT 3;

-- 8. Aggregate functions (COUNT, SUM, AVG, MIN, MAX)
SELECT COUNT(*) FROM users;
SELECT AVG(salary), MIN(salary), MAX(salary), SUM(salary) FROM users;
SELECT COUNT(name), AVG(age) FROM users;

-- 9. GROUP BY with aggregates
SELECT city, COUNT(*) FROM users GROUP BY city;
SELECT city, AVG(salary), MIN(age), MAX(age) FROM users GROUP BY city;

-- 10. INNER JOIN
SELECT users.name, orders.product, orders.amount
FROM users
INNER JOIN orders ON users.name = orders.user_name;

-- 11. JOIN with GROUP BY
SELECT users.name, users.city, COUNT(orders.id)
FROM users
INNER JOIN orders ON users.name = orders.user_name
GROUP BY users.name, users.city;

-- 12. INSERT INTO
INSERT INTO users VALUES ('Iris', 27, 'Seattle', 68000);

-- 13. Verify INSERT
SELECT * FROM users WHERE name = 'Iris';

-- 14. SAVE to CSV
SAVE users TO 'export_users.csv';
