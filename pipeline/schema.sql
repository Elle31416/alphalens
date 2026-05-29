-- AlphaLens PostgreSQL Schema
-- Automatically run by Docker on first startup

-- ─── Tickers ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tickers (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10) UNIQUE NOT NULL,
    company     VARCHAR(100) NOT NULL,
    -- LinkedIn identifiers
    linkedin_company_id  VARCHAR(50),
    -- Amazon key ASINs (comma-separated)
    amazon_asins TEXT,
    -- App Store / Play Store IDs
    ios_app_id    VARCHAR(50),
    android_pkg   VARCHAR(100),
    -- SEC CIK number
    sec_cik       VARCHAR(20),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Raw signal inputs ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_signals (
    id          BIGSERIAL PRIMARY KEY,
    ticker      VARCHAR(10) NOT NULL REFERENCES tickers(symbol),
    source      VARCHAR(20) NOT NULL,  -- linkedin|amazon|appstore|sec
    payload     JSONB       NOT NULL,
    scraped_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS raw_signals_ticker_idx   ON raw_signals(ticker);
CREATE INDEX IF NOT EXISTS raw_signals_source_idx   ON raw_signals(source);
CREATE INDEX IF NOT EXISTS raw_signals_scraped_idx  ON raw_signals(scraped_at DESC);

-- ─── Processed / AI signals ───────────────────────────────────
CREATE TABLE IF NOT EXISTS processed_signals (
    id              BIGSERIAL   PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL REFERENCES tickers(symbol),
    run_date        DATE        NOT NULL DEFAULT CURRENT_DATE,
    -- Individual source signals
    hiring_signal   JSONB,
    pricing_signal  JSONB,
    rating_signal   JSONB,
    filing_signal   JSONB,
    -- Composite output
    composite_score SMALLINT,           -- 0–100
    confidence_low  SMALLINT,
    confidence_high SMALLINT,
    overall_signal  VARCHAR(20),        -- strong_buy|buy|neutral|sell
    analyst_bullets TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, run_date)
);

CREATE INDEX IF NOT EXISTS proc_signals_ticker_date ON processed_signals(ticker, run_date DESC);
CREATE INDEX IF NOT EXISTS proc_signals_score       ON processed_signals(composite_score DESC);

-- ─── Backtest results ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backtest_results (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    signal_date     DATE        NOT NULL,
    alphalens_signal VARCHAR(20),
    composite_score  SMALLINT,
    key_evidence     TEXT[],
    actual_result    TEXT,
    actual_move_pct  NUMERIC(6,2),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Seed default watchlist ───────────────────────────────────
INSERT INTO tickers (symbol, company, amazon_asins, sec_cik) VALUES
    ('AAPL',  'Apple Inc.',             'B0BDHB9Y8H',  '0000320193'),
    ('MSFT',  'Microsoft Corporation',  'B09DKJ3WPJ',  '0000789019'),
    ('AMZN',  'Amazon.com Inc.',        'B08H75RTZ8',  '0001018724'),
    ('GOOGL', 'Alphabet Inc.',          'B09CXSBSQX',  '0001652044'),
    ('META',  'Meta Platforms Inc.',    'B0BZZ3NFKB',  '0001326801'),
    ('NVDA',  'NVIDIA Corporation',     'B07QP84KLQ',  '0001045810')
ON CONFLICT (symbol) DO NOTHING;
