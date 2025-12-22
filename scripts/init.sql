-- 创建数据库用户和授权
CREATE USER IF NOT EXISTS 'legal_user'@'%' IDENTIFIED BY 'legal_password';
GRANT ALL PRIVILEGES ON legal_db.* TO 'legal_user'@'%';
FLUSH PRIVILEGES;