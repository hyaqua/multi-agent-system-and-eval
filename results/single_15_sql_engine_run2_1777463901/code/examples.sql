-- Example SQL queries demonstrating all features
-- Run with: python main.py then '.load examples.sql'
-- Or copy-paste into the REPL

-- 1. LOAD tables
LOAD users FROM 'users.csv';
LOAD orders FROM 'orders.csv';
LOAD departments FROM 'departments.csv';

-- 2. SELECT * (all columns)
SELECT * FROM users;

-- 3. SELECT specific columns
SELECT name, age, city FROM users;

-- 4. WHERE with comparison operators
SELECT name, age FROM users WHERE age > 30;
SELECT name, salary FROM users WHERE salary >= 75000;
SELECT name, city FROM users WHERE city = 'New York';
SELECT name, age FROM users WHERE age != 22;
SELECT name, salary FROM users WHERE salary < 70000;

-- 5. WHERE with AND
SELECT name, age, city FROM users WHERE age > 25 AND city = 'Chicago';

-- 6. WHERE with OR
SELECT name, city FROM users WHERE city = 'New York' OR city = 'Los Angeles';

-- 7. ORDER BY ASC
SELECT name, age FROM users ORDER BY age ASC;

-- 8. ORDER BY DESC
SELECT name, salary FROM users ORDER BY salary DESC;

-- 9. ORDER BY multiple columns
SELECT city, name, age FROM users ORDER BY city ASC, age DESC;

-- 10. LIMIT
SELECT name, salary FROM users ORDER BY salary DESC LIMIT 3;

-- 11. COUNT aggregate
SELECT COUNT(*) FROM users;
SELECT COUNT(salary) FROM users;

-- 12. SUM aggregate
SELECT SUM(salary) FROM users;

-- 13. AVG aggregate
SELECT AVG(age) FROM users;

-- 14. MIN and MAX
SELECT MIN(salary), MAX(salary) FROM users;

-- 15. GROUP BY with aggregates
SELECT city, COUNT(*), AVG(salary) FROM users GROUP BY city;

-- 16. GROUP BY with multiple aggregates
SELECT city, COUNT(*), MIN(age), MAX(age), AVG(salary) FROM users GROUP BY city;

-- 17. INNER JOIN
SELECT users.name, orders.product, orders.amount FROM users INNER JOIN orders ON users.id = orders.user_id;

-- 18. JOIN with WHERE
SELECT users.name, orders.product, orders.amount FROM users INNER JOIN orders ON users.id = orders.user_id WHERE orders.amount > 100;

-- 19. JOIN with ORDER BY and LIMIT
SELECT users.name, orders.product, orders.amount FROM users INNER JOIN orders ON users.id = orders.user_id ORDER BY orders.amount DESC LIMIT 5;

-- 20. INSERT INTO
INSERT INTO users VALUES ('11', 'Kara', '26', 'kara@example.com', 'Boston', '55000');

-- Verify insert
SELECT * FROM users WHERE name = 'Kara';

-- 21. SAVE to file
SAVE users TO 'users_export.csv';
