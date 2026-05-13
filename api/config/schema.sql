CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(20) NOT NULL UNIQUE,
    password TEXT NOT NULL,
    email TEXT DEFAULT '',
    trades_count INTEGER DEFAULT 0,
    friendrequests_count INTEGER DEFAULT 0,
    messages_count INTEGER DEFAULT 0,
    messages JSONB DEFAULT '[]',
    admin BOOLEAN DEFAULT FALSE,
    equipped_items JSONB DEFAULT '[]',
    version VARCHAR(20) DEFAULT '1',
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS balances (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    robux INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS user_groups (
    userid INTEGER REFERENCES users(id) ON DELETE CASCADE,
    groupid INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (userid, groupid)
);

CREATE TABLE IF NOT EXISTS trades (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    inbound_trades JSONB DEFAULT '[]',
    outbound_trades JSONB DEFAULT '[]',
    inactive_trades JSONB DEFAULT '[]',
    completed_trades JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS inventory (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    items JSONB DEFAULT '[]'
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

CREATE TABLE IF NOT EXISTS followers (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    followers JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS followings (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    followings JSONB DEFAULT '[]'
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