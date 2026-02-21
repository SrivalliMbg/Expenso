-- Migration: Add user_id to accounts so dashboard shows per-user data
-- Run this if your accounts table does not have a user_id column yet.

-- Add user_id column (nullable so existing rows are valid)
ALTER TABLE accounts ADD COLUMN user_id INT NULL;

-- Optional: Link existing accounts to a default user (e.g. first user) if you have a single user
-- UPDATE accounts SET user_id = (SELECT id FROM users LIMIT 1) WHERE user_id IS NULL;

-- Optional: Add foreign key to users table
-- ALTER TABLE accounts ADD CONSTRAINT fk_accounts_user FOREIGN KEY (user_id) REFERENCES users(id);
