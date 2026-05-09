CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    email TEXT DEFAULT '',
    tradescount INTEGER DEFAULT 0,
    friendrequestscount INTEGER DEFAULT 0,
    messagescount INTEGER DEFAULT 0,
    messages JSONB DEFAULT '[]',
    items JSONB DEFAULT '[]',
    admin BOOLEAN DEFAULT FALSE,
    equippeditems JSONB DEFAULT '[]',
    version VARCHAR(20) DEFAULT '1'
);

CREATE TABLE IF NOT EXISTS balances (
    userid INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    robux INTEGER DEFAULT 0
);