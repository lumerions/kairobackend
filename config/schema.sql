CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(20) NOT NULL UNIQUE,
    password TEXT NOT NULL,
    trades_count INTEGER DEFAULT 0,
    friendrequests_count INTEGER DEFAULT 0,
    friends_count INTEGER DEFAULT 0,
    followers_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    messages_count INTEGER DEFAULT 0,
    messages JSONB DEFAULT '[]',
    admin BOOLEAN DEFAULT FALSE,
    version VARCHAR(20) DEFAULT '1',
    createdAt TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    twofa_enabled BOOLEAN DEFAULT FALSE,
    twofa_secret TEXT,
    posts INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS balances (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    robux INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    description VARCHAR(1000) NOT NULL,
    groupcreator VARCHAR(20) NOT NULL,
    groupcreator_id INTEGER REFERENCES users(id)
    name VARCHAR(20) NOT NULL UNIQUE,
    groupshout VARCHAR(255) DEFAULT '',
    last_groupshout_time TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trades (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    inbound_trades JSONB DEFAULT '[]',
    outbound_trades JSONB DEFAULT '[]',
    inactive_trades JSONB DEFAULT '[]',
    completed_trades JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT exists inventory (
    userid INTEGER REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL,
    serial_number INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (userid, item_id)
);

CREATE TABLE IF NOT EXISTS membership (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    membership VARCHAR(30) DEFAULT 'Free',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS catalog_items (
    id SERIAL PRIMARY KEY,
    asset_type INTEGER,
    name TEXT NOT NULL,
    limited_status VARCHAR(30),
    description VARCHAR(1000) DEFAULT '',
    creator_userid INTEGER,
    creator_name TEXT,
    offsale_deadline TIMESTAMP,
    sale_count INTEGER DEFAULT 0,
    item_type TEXT,
    favorite_count INTEGER DEFAULT 0,
    for_sale BOOLEAN DEFAULT FALSE,
    price INTEGER,
    lowest_price INTEGER,
    price_status TEXT,
    available_stock INTEGER,
    serial_count INTEGER,
    moderation_status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS friendrequests (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    requests JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS friends (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    friends JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    following_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    userid INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    location TEXT,
    user_agent TEXT
);

CREATE TABLE IF NOT EXISTS additional_user_data (
    userid INTEGER REFERENCES users(id) ON DELETE CASCADE,
    equipped_items JSONB DEFAULT '[]',
    email TEXT DEFAULT '',
    vip_server_status VARCHAR(100) DEFAULT 'All Users',
    message_status VARCHAR(100) DEFAULT 'All Users',
    follow_status VARCHAR(100) DEFAULT 'All Users',
    inventory_status VARCHAR(100) DEFAULT 'All Users',
    trade_status VARCHAR(100) DEFAULT 'All Users',
    trade_filter VARCHAR(100) DEFAULT 'None',
    pending_email TEXT DEFAULT NULL,
    email_code VARCHAR(100) DEFAULT 'None',
    email_code_expiration TIMESTAMP DEFAULT NOW(),
    bio VARCHAR(1000) DEFAULT ''
);

CREATE TABLE IF NOT EXISTS forums (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    last_forum_post_time TIMESTAMP DEFAULT NULL,
    last_forum_post_username VARCHAR(20) DEFAULT NULL,
    threads INTEGER DEFAULT 0,
    posts INTEGER DEFAULT 0,
    forums JSONB DEFAULT '[]',
    threads_data JSONB DEFAULT '[]',
    posts_data JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS group_images (
    group_id INTEGER PRIMARY KEY,
    filename TEXT,
    content_type TEXT,
    data BYTEA,
    FOREIGN KEY (group_id)
        REFERENCES groups(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_store (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    item_name VARCHAR(25) NOT NULL,
    price INTEGER NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_roles (
    group_id INTEGER NOT NULL,
    role VARCHAR(25) NOT NULL,
    description VARCHAR(100) NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_audit_log (
    group_id INTEGER NOT NULL,
    audit_user_id INTEGER NOT NULL,
    audit_log_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(25) DEFAULT 'Member',
    primary_group BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_wall (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    user_id INTEGER,
    blurb VARCHAR(1000) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS group_store_images (
    store_item_id INTEGER PRIMARY KEY,
    filename TEXT,
    content_type TEXT,
    data BYTEA,
    FOREIGN KEY (store_item_id)
        REFERENCES group_store(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_transactions (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (group_id)
        REFERENCES groups(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS additional_group_data (
    group_id INTEGER NOT NULL,
    group_funds INTEGER DEFAULT 0,
    sale_of_goods INTEGER DEFAULT 0,
    promoted_page_conversion_revenue INTEGER DEFAULT 0,
    game_page_conversion_revenue INTEGER DEFAULT 0,
    pending_sales INTEGER DEFAULT 0,
    allow_enemy_declarations BOOLEAN NOT NULL DEFAULT FALSE,
    group_funds_visible BOOLEAN NOT NULL DEFAULT FALSE,
    group_games_visible BOOLEAN NOT NULL DEFAULT TRUE,
    manual_approval BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS username_lower_unique
ON users (LOWER(username));
CREATE INDEX IF NOT EXISTS index_forums_id ON forums(id);
