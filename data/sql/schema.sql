-- =========================================================
-- Espelho do schema `public` do Supabase (banco real do grupo) — DDL só, sem dados.
-- Gerado a partir do catálogo do Postgres; enums gravados como código em inglês
-- (o app traduz em infra/postgres/models/base.py:Rotulo). RLS do Supabase fica de
-- fora (sem policies lá; local o dono da tabela ignora RLS de qualquer jeito).
-- =========================================================

BEGIN;

-- ---- enums ----
CREATE TYPE account_type_enum AS ENUM ('DOMESTIC', 'BUSINESS', 'COMMERCIAL');
CREATE TYPE billing_interval_enum AS ENUM ('MONTHLY', 'YEARLY');
CREATE TYPE category_enum AS ENUM ('FRUIT', 'VEGETABLE', 'DAIRY', 'MEAT', 'GRAIN', 'BEVERAGE', 'CLEANING', 'PERSONAL_HYGIENE');
CREATE TYPE conversation_type_enum AS ENUM ('PRIVATE', 'GROUP');
CREATE TYPE list_status_enum AS ENUM ('OPEN', 'COMPLETED', 'CANCELED');
CREATE TYPE message_type_enum AS ENUM ('TEXT', 'IMAGE', 'SYSTEM');
CREATE TYPE movement_type_enum AS ENUM ('IN', 'OUT', 'ADJUSTMENT');
CREATE TYPE payment_method_enum AS ENUM ('CREDIT_CARD', 'DEBIT_CARD', 'PIX', 'BOLETO');
CREATE TYPE product_list_status_enum AS ENUM ('PENDING', 'PURCHASED', 'REMOVED');
CREATE TYPE product_status_enum AS ENUM ('FRESH', 'NEAR_EXPIRATION', 'EXPIRED');
CREATE TYPE storage_place_enum AS ENUM ('FRIDGE', 'FREEZER', 'PANTRY', 'CABINET', 'SHELF');
CREATE TYPE subscription_status_enum AS ENUM ('TRIAL', 'ACTIVE', 'CANCELED', 'EXPIRED', 'DELINQUENT');
CREATE TYPE transaction_status_enum AS ENUM ('PENDING', 'PROCESSING', 'APPROVED', 'REJECTED', 'CANCELED', 'ERROR');
CREATE TYPE unit_of_measure_enum AS ENUM ('KILOGRAM', 'GRAM', 'LITER', 'MILLILITER', 'UNIT', 'DOZEN', 'PACKAGE');
CREATE TYPE user_role_enum AS ENUM ('USER', 'ADMIN');

-- ---- sequences ----
CREATE SEQUENCE discard_id_seq AS integer;
CREATE SEQUENCE message_attachments_id_seq AS integer;
CREATE SEQUENCE messages_id_seq AS integer;
CREATE SEQUENCE plans_id_seq AS integer;
CREATE SEQUENCE products_id_seq AS integer;
CREATE SEQUENCE recipe_ingredients_id_seq AS integer;
CREATE SEQUENCE recipe_suggestions_id_seq AS integer;
CREATE SEQUENCE recipes_id_seq AS integer;
CREATE SEQUENCE requests_id_seq AS integer;
CREATE SEQUENCE shopping_list_products_id_seq AS integer;
CREATE SEQUENCE stock_movements_id_seq AS integer;
CREATE SEQUENCE stock_products_id_seq AS integer;
CREATE SEQUENCE stocks_id_seq AS integer;
CREATE SEQUENCE transaction_events_id_seq AS integer;
CREATE SEQUENCE user_groups_id_seq AS integer;

-- ---- tabelas ----
CREATE TABLE conversation_participants (
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL,
    joined_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    left_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_type conversation_type_enum NOT NULL,
    group_id uuid,
    name character varying,
    pair_key character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE discard (
    id integer DEFAULT nextval('discard_id_seq'::regclass) NOT NULL,
    stock_product_id integer NOT NULL,
    reason text,
    date timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE groups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying NOT NULL,
    banner_picture text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp without time zone,
    owner_id uuid
);

CREATE TABLE message_attachments (
    id integer DEFAULT nextval('message_attachments_id_seq'::regclass) NOT NULL,
    message_id integer NOT NULL,
    file_url text NOT NULL,
    file_name character varying,
    mime_type character varying NOT NULL,
    file_size integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE message_reads (
    message_id integer NOT NULL,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL,
    read_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE messages (
    id integer DEFAULT nextval('messages_id_seq'::regclass) NOT NULL,
    conversation_id uuid NOT NULL,
    sender_id uuid NOT NULL,
    message_type message_type_enum NOT NULL,
    content text,
    related_shopping_list_product_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE plans (
    id integer DEFAULT nextval('plans_id_seq'::regclass) NOT NULL,
    name character varying NOT NULL,
    description text,
    price numeric(10,2) DEFAULT 0 NOT NULL,
    billing_interval billing_interval_enum,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp without time zone,
    plan_code character varying(20) NOT NULL
);

CREATE TABLE products (
    id integer DEFAULT nextval('products_id_seq'::regclass) NOT NULL,
    name character varying NOT NULL,
    category category_enum NOT NULL,
    storage_place storage_place_enum NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    unit_of_measure unit_of_measure_enum NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE recipe_ingredients (
    id integer DEFAULT nextval('recipe_ingredients_id_seq'::regclass) NOT NULL,
    recipe_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity numeric,
    unit character varying,
    required boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE recipe_suggestions (
    id integer DEFAULT nextval('recipe_suggestions_id_seq'::regclass) NOT NULL,
    recipe_id integer NOT NULL,
    stock_id integer NOT NULL,
    matched_ingredients integer DEFAULT 0 NOT NULL,
    missing_ingredients integer DEFAULT 0 NOT NULL,
    nearest_expire_date date,
    score numeric,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE recipes (
    id integer DEFAULT nextval('recipes_id_seq'::regclass) NOT NULL,
    name character varying NOT NULL,
    description text,
    instructions text,
    domestic_only boolean DEFAULT true NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE requests (
    id integer DEFAULT nextval('requests_id_seq'::regclass) NOT NULL,
    user_id uuid NOT NULL,
    product_id integer NOT NULL,
    stock_id integer NOT NULL,
    quantity integer NOT NULL,
    description text,
    picture text,
    date date DEFAULT CURRENT_DATE NOT NULL,
    conversation_id uuid,
    message_id integer,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE shopping_list_products (
    id integer DEFAULT nextval('shopping_list_products_id_seq'::regclass) NOT NULL,
    list_id uuid NOT NULL,
    product_id integer NOT NULL,
    status product_list_status_enum,
    quantity integer DEFAULT 1 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE shopping_lists (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    date date DEFAULT CURRENT_DATE NOT NULL,
    stock_id integer NOT NULL,
    status list_status_enum NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE stock_movements (
    id integer DEFAULT nextval('stock_movements_id_seq'::regclass) NOT NULL,
    stock_product_id integer NOT NULL,
    user_id uuid NOT NULL,
    movement_type movement_type_enum NOT NULL,
    quantity integer NOT NULL,
    date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stock_products (
    id integer DEFAULT nextval('stock_products_id_seq'::regclass) NOT NULL,
    product_id integer NOT NULL,
    stock_id integer NOT NULL,
    quantity integer NOT NULL,
    minimal_quantity integer,
    expire_date date NOT NULL,
    product_status product_status_enum,
    category category_enum NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE stocks (
    id integer DEFAULT nextval('stocks_id_seq'::regclass) NOT NULL,
    group_id uuid NOT NULL,
    name character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp without time zone
);

CREATE TABLE subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    plan_id integer NOT NULL,
    status subscription_status_enum DEFAULT 'TRIAL'::subscription_status_enum NOT NULL,
    started_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    current_period_start timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    current_period_end timestamp without time zone,
    canceled_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp without time zone
);

CREATE TABLE transaction_events (
    id integer DEFAULT nextval('transaction_events_id_seq'::regclass) NOT NULL,
    transaction_id uuid NOT NULL,
    status transaction_status_enum NOT NULL,
    message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    subscription_id uuid,
    plan_id integer NOT NULL,
    amount numeric(10,2) NOT NULL,
    payment_method payment_method_enum NOT NULL,
    fake_card_last4 character varying(4),
    fake_pix_key character varying,
    status transaction_status_enum DEFAULT 'PENDING'::transaction_status_enum NOT NULL,
    queue_job_id character varying,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 3 NOT NULL,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    queued_at timestamp without time zone,
    processed_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    idempotency_key character varying(120) NOT NULL
);

CREATE TABLE user_groups (
    id integer DEFAULT nextval('user_groups_id_seq'::regclass) NOT NULL,
    user_id uuid NOT NULL,
    group_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying NOT NULL,
    birth_date date,
    account_type account_type_enum NOT NULL,
    email character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp without time zone,
    role user_role_enum DEFAULT 'USER'::user_role_enum NOT NULL,
    hash_password character varying,
    senha character varying(100) DEFAULT 'VAZIO'::character varying
);

-- ---- sequences pertencem às colunas ----
ALTER SEQUENCE discard_id_seq OWNED BY discard.id;
ALTER SEQUENCE message_attachments_id_seq OWNED BY message_attachments.id;
ALTER SEQUENCE messages_id_seq OWNED BY messages.id;
ALTER SEQUENCE plans_id_seq OWNED BY plans.id;
ALTER SEQUENCE products_id_seq OWNED BY products.id;
ALTER SEQUENCE recipe_ingredients_id_seq OWNED BY recipe_ingredients.id;
ALTER SEQUENCE recipe_suggestions_id_seq OWNED BY recipe_suggestions.id;
ALTER SEQUENCE recipes_id_seq OWNED BY recipes.id;
ALTER SEQUENCE requests_id_seq OWNED BY requests.id;
ALTER SEQUENCE shopping_list_products_id_seq OWNED BY shopping_list_products.id;
ALTER SEQUENCE stock_movements_id_seq OWNED BY stock_movements.id;
ALTER SEQUENCE stock_products_id_seq OWNED BY stock_products.id;
ALTER SEQUENCE stocks_id_seq OWNED BY stocks.id;
ALTER SEQUENCE transaction_events_id_seq OWNED BY transaction_events.id;
ALTER SEQUENCE user_groups_id_seq OWNED BY user_groups.id;

-- ---- constraints (PK/UNIQUE, CHECK, FK) ----
ALTER TABLE conversation_participants ADD CONSTRAINT conversation_participants_pkey PRIMARY KEY (conversation_id, user_id);
ALTER TABLE conversations ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);
ALTER TABLE discard ADD CONSTRAINT discard_pkey PRIMARY KEY (id);
ALTER TABLE groups ADD CONSTRAINT groups_pkey PRIMARY KEY (id);
ALTER TABLE message_attachments ADD CONSTRAINT message_attachments_pkey PRIMARY KEY (id);
ALTER TABLE message_reads ADD CONSTRAINT message_reads_pkey PRIMARY KEY (message_id, user_id);
ALTER TABLE messages ADD CONSTRAINT messages_pkey PRIMARY KEY (id);
ALTER TABLE plans ADD CONSTRAINT plans_pkey PRIMARY KEY (id);
ALTER TABLE products ADD CONSTRAINT products_pkey PRIMARY KEY (id);
ALTER TABLE recipe_ingredients ADD CONSTRAINT recipe_ingredients_pkey PRIMARY KEY (id);
ALTER TABLE recipe_suggestions ADD CONSTRAINT recipe_suggestions_pkey PRIMARY KEY (id);
ALTER TABLE recipes ADD CONSTRAINT recipes_pkey PRIMARY KEY (id);
ALTER TABLE requests ADD CONSTRAINT requests_pkey PRIMARY KEY (id);
ALTER TABLE shopping_list_products ADD CONSTRAINT shopping_list_products_pkey PRIMARY KEY (id);
ALTER TABLE shopping_lists ADD CONSTRAINT shopping_lists_pkey PRIMARY KEY (id);
ALTER TABLE stock_movements ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (id);
ALTER TABLE stock_products ADD CONSTRAINT stock_products_pkey PRIMARY KEY (id);
ALTER TABLE stocks ADD CONSTRAINT stocks_pkey PRIMARY KEY (id);
ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);
ALTER TABLE transaction_events ADD CONSTRAINT transaction_events_pkey PRIMARY KEY (id);
ALTER TABLE transactions ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);
ALTER TABLE user_groups ADD CONSTRAINT user_groups_pkey PRIMARY KEY (id);
ALTER TABLE users ADD CONSTRAINT users_pkey PRIMARY KEY (id);
ALTER TABLE conversations ADD CONSTRAINT uq_pair UNIQUE (pair_key);
ALTER TABLE messages ADD CONSTRAINT uq_messages_id_conversation UNIQUE (id, conversation_id);
ALTER TABLE plans ADD CONSTRAINT uq_plans_plan_code UNIQUE (plan_code);
ALTER TABLE recipe_ingredients ADD CONSTRAINT uq_recipe_ingredients_recipe_product UNIQUE (recipe_id, product_id);
ALTER TABLE shopping_list_products ADD CONSTRAINT uq_shopping_list_products_list_product UNIQUE (list_id, product_id);
ALTER TABLE stock_products ADD CONSTRAINT uq_stock_products_product_stock_expire UNIQUE (product_id, stock_id, expire_date);
ALTER TABLE transactions ADD CONSTRAINT uq_transactions_idempotency_key UNIQUE (idempotency_key);
ALTER TABLE user_groups ADD CONSTRAINT uq_user_groups_user_group UNIQUE (user_id, group_id);
ALTER TABLE conversations ADD CONSTRAINT chk_conversation_type_group CHECK ((((conversation_type = 'GROUP'::conversation_type_enum) AND (group_id IS NOT NULL)) OR ((conversation_type = 'PRIVATE'::conversation_type_enum) AND (group_id IS NULL))));
ALTER TABLE groups ADD CONSTRAINT chk_active_groups_require_owner CHECK (((deleted_at IS NOT NULL) OR (owner_id IS NOT NULL)));
ALTER TABLE requests ADD CONSTRAINT chk_requests_message_conversation CHECK (((message_id IS NULL) OR (conversation_id IS NOT NULL)));
ALTER TABLE transactions ADD CONSTRAINT chk_transactions_processed_at CHECK ((((status = ANY (ARRAY['PENDING'::transaction_status_enum, 'PROCESSING'::transaction_status_enum])) AND (processed_at IS NULL)) OR (status <> ALL (ARRAY['PENDING'::transaction_status_enum, 'PROCESSING'::transaction_status_enum]))));
ALTER TABLE transactions ADD CONSTRAINT transactions_amount_check CHECK ((amount > (0)::numeric));
ALTER TABLE conversation_participants ADD CONSTRAINT fk_conversation_participants_conversation_id_conversations FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE;
ALTER TABLE conversation_participants ADD CONSTRAINT fk_conversation_participants_user_id_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE conversations ADD CONSTRAINT fk_conversations_group_id_groups FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL;
ALTER TABLE discard ADD CONSTRAINT fk_discard_stock_product_id_stock_products FOREIGN KEY (stock_product_id) REFERENCES stock_products(id) ON DELETE CASCADE;
ALTER TABLE groups ADD CONSTRAINT fk_groups_owner_id_users FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE message_attachments ADD CONSTRAINT fk_message_attachments_message_id_messages FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE;
ALTER TABLE message_reads ADD CONSTRAINT fk_message_reads_conversation_id_participants FOREIGN KEY (conversation_id, user_id) REFERENCES conversation_participants(conversation_id, user_id) ON DELETE CASCADE;
ALTER TABLE message_reads ADD CONSTRAINT fk_message_reads_message_id_messages FOREIGN KEY (message_id, conversation_id) REFERENCES messages(id, conversation_id) ON DELETE CASCADE;
ALTER TABLE messages ADD CONSTRAINT fk_messages_conversation_id_conversations FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE;
ALTER TABLE messages ADD CONSTRAINT fk_messages_conversation_id_participants FOREIGN KEY (conversation_id, sender_id) REFERENCES conversation_participants(conversation_id, user_id);
ALTER TABLE messages ADD CONSTRAINT fk_messages_related_shopping_list_product_id_slp FOREIGN KEY (related_shopping_list_product_id) REFERENCES shopping_list_products(id) ON DELETE SET NULL;
ALTER TABLE messages ADD CONSTRAINT fk_messages_sender_id_users FOREIGN KEY (sender_id) REFERENCES users(id);
ALTER TABLE recipe_ingredients ADD CONSTRAINT fk_recipe_ingredients_product_id_products FOREIGN KEY (product_id) REFERENCES products(id);
ALTER TABLE recipe_ingredients ADD CONSTRAINT fk_recipe_ingredients_recipe_id_recipes FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE;
ALTER TABLE recipe_suggestions ADD CONSTRAINT fk_recipe_suggestions_recipe_id_recipes FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE;
ALTER TABLE recipe_suggestions ADD CONSTRAINT fk_recipe_suggestions_stock_id_stocks FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE;
ALTER TABLE requests ADD CONSTRAINT fk_requests_conversation_id_conversations FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL;
ALTER TABLE requests ADD CONSTRAINT fk_requests_message_id_messages FOREIGN KEY (message_id, conversation_id) REFERENCES messages(id, conversation_id) ON DELETE SET NULL;
ALTER TABLE requests ADD CONSTRAINT fk_requests_product_id_products FOREIGN KEY (product_id) REFERENCES products(id);
ALTER TABLE requests ADD CONSTRAINT fk_requests_stock_id_stocks FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE;
ALTER TABLE requests ADD CONSTRAINT fk_requests_user_id_users FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE shopping_list_products ADD CONSTRAINT fk_shopping_list_products_list_id_shopping_lists FOREIGN KEY (list_id) REFERENCES shopping_lists(id) ON DELETE CASCADE;
ALTER TABLE shopping_list_products ADD CONSTRAINT fk_shopping_list_products_product_id_products FOREIGN KEY (product_id) REFERENCES products(id);
ALTER TABLE shopping_lists ADD CONSTRAINT fk_shopping_lists_stock_id_stocks FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE;
ALTER TABLE stock_movements ADD CONSTRAINT fk_stock_movements_stock_product_id_stock_products FOREIGN KEY (stock_product_id) REFERENCES stock_products(id) ON DELETE CASCADE;
ALTER TABLE stock_movements ADD CONSTRAINT fk_stock_movements_user_id_users FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE stock_products ADD CONSTRAINT fk_stock_products_product_id_products FOREIGN KEY (product_id) REFERENCES products(id);
ALTER TABLE stock_products ADD CONSTRAINT fk_stock_products_stock_id_stocks FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE;
ALTER TABLE stocks ADD CONSTRAINT fk_stocks_group_id_groups FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE;
ALTER TABLE subscriptions ADD CONSTRAINT fk_subscriptions_plan_id_plans FOREIGN KEY (plan_id) REFERENCES plans(id);
ALTER TABLE subscriptions ADD CONSTRAINT fk_subscriptions_user_id_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE transaction_events ADD CONSTRAINT fk_transaction_events_transaction_id_transactions FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE;
ALTER TABLE transactions ADD CONSTRAINT fk_transactions_plan_id_plans FOREIGN KEY (plan_id) REFERENCES plans(id);
ALTER TABLE transactions ADD CONSTRAINT fk_transactions_subscription_id_subscriptions FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE;
ALTER TABLE transactions ADD CONSTRAINT fk_transactions_user_id_users FOREIGN KEY (user_id) REFERENCES users(id);
ALTER TABLE user_groups ADD CONSTRAINT fk_user_groups_group_id_groups FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE;
ALTER TABLE user_groups ADD CONSTRAINT fk_user_groups_user_id_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- ---- índices ----
CREATE INDEX idx_conversation_participants_user ON conversation_participants USING btree (user_id);
CREATE INDEX idx_conversations_group ON conversations USING btree (group_id);
CREATE INDEX idx_groups_deleted_at ON groups USING btree (deleted_at);
CREATE INDEX idx_groups_owner ON groups USING btree (owner_id);
CREATE INDEX idx_message_attachments_message ON message_attachments USING btree (message_id);
CREATE INDEX idx_message_reads_user ON message_reads USING btree (user_id);
CREATE INDEX idx_messages_conversation_created ON messages USING btree (conversation_id, created_at);
CREATE INDEX idx_messages_sender ON messages USING btree (sender_id);
CREATE INDEX idx_plans_deleted_at ON plans USING btree (deleted_at);
CREATE INDEX idx_products_category ON products USING btree (category);
CREATE INDEX idx_products_storage_place ON products USING btree (storage_place);
CREATE INDEX idx_recipe_ingredients_product ON recipe_ingredients USING btree (product_id);
CREATE INDEX idx_recipe_ingredients_recipe ON recipe_ingredients USING btree (recipe_id);
CREATE INDEX idx_recipe_suggestions_expire_date ON recipe_suggestions USING btree (nearest_expire_date);
CREATE INDEX idx_recipe_suggestions_recipe ON recipe_suggestions USING btree (recipe_id);
CREATE INDEX idx_recipe_suggestions_stock ON recipe_suggestions USING btree (stock_id);
CREATE INDEX idx_requests_conversation ON requests USING btree (conversation_id);
CREATE INDEX idx_requests_product ON requests USING btree (product_id);
CREATE INDEX idx_requests_stock ON requests USING btree (stock_id);
CREATE INDEX idx_requests_user ON requests USING btree (user_id);
CREATE INDEX idx_shopping_list_products_list ON shopping_list_products USING btree (list_id);
CREATE INDEX idx_shopping_list_products_product ON shopping_list_products USING btree (product_id);
CREATE INDEX idx_shopping_lists_stock ON shopping_lists USING btree (stock_id);
CREATE INDEX idx_stock_movements_date ON stock_movements USING btree (date);
CREATE INDEX idx_stock_movements_stock_product ON stock_movements USING btree (stock_product_id);
CREATE INDEX idx_stock_movements_user ON stock_movements USING btree (user_id);
CREATE INDEX idx_stock_products_expire_date ON stock_products USING btree (expire_date);
CREATE INDEX idx_stock_products_product ON stock_products USING btree (product_id);
CREATE INDEX idx_stock_products_status ON stock_products USING btree (product_status);
CREATE INDEX idx_stock_products_stock ON stock_products USING btree (stock_id);
CREATE INDEX idx_stocks_deleted_at ON stocks USING btree (deleted_at);
CREATE INDEX idx_stocks_group ON stocks USING btree (group_id);
CREATE INDEX idx_subscriptions_deleted_at ON subscriptions USING btree (deleted_at);
CREATE INDEX idx_subscriptions_plan ON subscriptions USING btree (plan_id);
CREATE INDEX idx_subscriptions_status ON subscriptions USING btree (status);
CREATE INDEX idx_subscriptions_user ON subscriptions USING btree (user_id);
CREATE INDEX idx_transaction_events_transaction ON transaction_events USING btree (transaction_id, created_at);
CREATE INDEX idx_transactions_created_at ON transactions USING btree (created_at);
CREATE INDEX idx_transactions_plan ON transactions USING btree (plan_id);
CREATE INDEX idx_transactions_status ON transactions USING btree (status);
CREATE INDEX idx_transactions_subscription ON transactions USING btree (subscription_id);
CREATE INDEX idx_transactions_user ON transactions USING btree (user_id);
CREATE INDEX idx_user_groups_group ON user_groups USING btree (group_id);
CREATE INDEX idx_user_groups_user ON user_groups USING btree (user_id);
CREATE INDEX idx_users_deleted_at ON users USING btree (deleted_at);
CREATE UNIQUE INDEX uq_plans_name_active ON plans USING btree (name) WHERE (deleted_at IS NULL);
CREATE UNIQUE INDEX uq_subscriptions_one_active_per_user ON subscriptions USING btree (user_id) WHERE ((status = ANY (ARRAY['TRIAL'::subscription_status_enum, 'ACTIVE'::subscription_status_enum])) AND (deleted_at IS NULL));
CREATE UNIQUE INDEX uq_users_email_active ON users USING btree (email) WHERE (deleted_at IS NULL);

-- ---- funções e procedures ----
CREATE OR REPLACE FUNCTION fn_compute_product_status_enum(p_expire_date date, p_warn_days integer DEFAULT 3)
 RETURNS product_status_enum
 LANGUAGE sql
 STABLE
AS $function$
    SELECT CASE
        WHEN p_expire_date < CURRENT_DATE THEN 'EXPIRED'::product_status_enum
        WHEN p_expire_date <= CURRENT_DATE + p_warn_days THEN 'NEAR_EXPIRATION'::product_status_enum
        ELSE 'FRESH'::product_status_enum
    END;
$function$;

CREATE OR REPLACE FUNCTION fn_compute_product_status(p_expire_date date, p_warn_days integer DEFAULT 3)
 RETURNS character varying
 LANGUAGE sql
 STABLE
AS $function$
    SELECT CASE fn_compute_product_status_enum(p_expire_date, p_warn_days)
        WHEN 'EXPIRED'::product_status_enum         THEN 'Vencido'
        WHEN 'NEAR_EXPIRATION'::product_status_enum THEN 'Próximo do vencimento'
        WHEN 'FRESH'::product_status_enum           THEN 'Fresco'
    END;
$function$;

CREATE OR REPLACE FUNCTION fn_log_transaction_status_change()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO transaction_events (transaction_id, status, message)
        VALUES (NEW.id, NEW.status, NULL);
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION fn_low_stock_products(p_stock_id integer)
 RETURNS TABLE(stock_product_id integer, product_id integer, product_name character varying, quantity integer, minimal_quantity integer)
 LANGUAGE sql
 STABLE
AS $function$
    SELECT sp.id, sp.product_id, p.name, sp.quantity, sp.minimal_quantity
    FROM stock_products sp
    JOIN products p ON p.id = sp.product_id
    WHERE sp.stock_id = p_stock_id
      AND sp.minimal_quantity IS NOT NULL
      AND sp.quantity < sp.minimal_quantity;
$function$;

CREATE OR REPLACE FUNCTION fn_pair_key(p_user_a integer, p_user_b integer)
 RETURNS character varying
 LANGUAGE sql
 IMMUTABLE
AS $function$
    SELECT LEAST(p_user_a, p_user_b)::VARCHAR || '_' || GREATEST(p_user_a, p_user_b)::VARCHAR;
$function$;

CREATE OR REPLACE FUNCTION fn_set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION fn_suggest_recipes(p_stock_id integer)
 RETURNS TABLE(recipe_id integer, matched_ingredients integer, missing_ingredients integer, nearest_expire_date date, score numeric)
 LANGUAGE sql
 STABLE
AS $function$
    WITH ingredient_match AS (
        SELECT
            ri.recipe_id,
            ri.product_id,
            bool_or(sp.id IS NOT NULL)  AS in_stock,
            MIN(sp.expire_date)          AS earliest_expire_date
        FROM recipe_ingredients ri
        LEFT JOIN stock_products sp
            ON sp.product_id = ri.product_id
           AND sp.stock_id = p_stock_id
        GROUP BY ri.recipe_id, ri.product_id
    )
    SELECT
        recipe_id,
        COUNT(*) FILTER (WHERE in_stock)::INTEGER      AS matched_ingredients,
        COUNT(*) FILTER (WHERE NOT in_stock)::INTEGER  AS missing_ingredients,
        MIN(earliest_expire_date)                       AS nearest_expire_date,
        ROUND(COUNT(*) FILTER (WHERE in_stock)::NUMERIC / NULLIF(COUNT(*), 0), 2) AS score
    FROM ingredient_match
    GROUP BY recipe_id;
$function$;

CREATE OR REPLACE PROCEDURE sp_close_shopping_list(IN p_list_id integer)
 LANGUAGE plpgsql
AS $procedure$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM shopping_list_products
        WHERE list_id = p_list_id
          AND status NOT IN ('PURCHASED', 'REMOVED')
    ) THEN
        UPDATE shopping_lists
           SET status = 'COMPLETED'
         WHERE id = p_list_id;
    END IF;
END;
$procedure$;

CREATE OR REPLACE PROCEDURE sp_get_or_create_private_conversation(IN p_user_a integer, IN p_user_b integer, INOUT p_conversation_id integer DEFAULT NULL::integer)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_pair_key VARCHAR;
BEGIN
    v_pair_key := fn_pair_key(p_user_a, p_user_b);

    SELECT id INTO p_conversation_id
    FROM conversations
    WHERE pair_key = v_pair_key;

    IF p_conversation_id IS NULL THEN
        INSERT INTO conversations (conversation_type)
        VALUES ('PRIVATE')
        RETURNING id INTO p_conversation_id;

        INSERT INTO conversation_participants (conversation_id, user_id)
        VALUES (p_conversation_id, p_user_a), (p_conversation_id, p_user_b);
        -- trg_conversation_participants_pair_key seta o pair_key após o 2º insert acima
    END IF;
END;
$procedure$;

CREATE OR REPLACE PROCEDURE sp_purchase_shopping_list_item(IN p_list_id integer, IN p_product_id integer, IN p_stock_id integer, IN p_stock_product_id integer, IN p_quantity integer, IN p_expire_date date, IN p_user_id integer)
 LANGUAGE plpgsql
AS $procedure$
BEGIN
    UPDATE shopping_list_products
       SET status = 'PURCHASED'
     WHERE list_id = p_list_id
       AND product_id = p_product_id;

    INSERT INTO stock_products (id, product_id, stock_id, quantity, expire_date, category)
    SELECT p_stock_product_id, p_product_id, p_stock_id, 0, p_expire_date, category
    FROM products
    WHERE id = p_product_id
    ON CONFLICT (product_id, stock_id, expire_date) DO NOTHING;

    INSERT INTO stock_movements (stock_product_id, user_id, movement_type, quantity)
    VALUES (p_stock_product_id, p_user_id, 'IN', p_quantity);
    -- trg_stock_movements_apply soma p_quantity em stock_products.quantity
END;
$procedure$;

CREATE OR REPLACE FUNCTION trg_fn_conversation_participants_pair_key()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_conversation_type conversation_type_enum;
    v_participants       INTEGER[];
BEGIN
    SELECT conversation_type INTO v_conversation_type
    FROM conversations
    WHERE id = NEW.conversation_id;

    IF v_conversation_type = 'PRIVATE' THEN
        SELECT array_agg(user_id ORDER BY user_id) INTO v_participants
        FROM conversation_participants
        WHERE conversation_id = NEW.conversation_id;

        IF array_length(v_participants, 1) = 2 THEN
            UPDATE conversations
               SET pair_key = fn_pair_key(v_participants[1], v_participants[2])
             WHERE id = NEW.conversation_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION trg_fn_stock_movements_apply()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_delta        INTEGER;
    v_new_quantity INTEGER;
BEGIN
    -- ponytail: 'ADJUSTMENT' usa o sinal de NEW.quantity direto (positivo soma, negativo subtrai).
    -- Se precisar de um tipo de ajuste explicitamente absoluto, separar em outra coluna/enum.
    v_delta := CASE NEW.movement_type
        WHEN 'IN'  THEN NEW.quantity
        WHEN 'OUT' THEN -NEW.quantity
        ELSE NEW.quantity
    END;

    UPDATE stock_products
       SET quantity = quantity + v_delta
     WHERE id = NEW.stock_product_id
     RETURNING quantity INTO v_new_quantity;

    IF v_new_quantity < 0 THEN
        RAISE EXCEPTION 'stock_movements: quantidade resultante negativa para stock_product_id %', NEW.stock_product_id;
    END IF;

    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION trg_fn_stock_products_set_status()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    -- usa a versão que retorna o enum (valores em inglês), não a versão
    -- de exibição em português, já que a coluna é do tipo product_status_enum.
    NEW.product_status := fn_compute_product_status_enum(NEW.expire_date);
    RETURN NEW;
END;
$function$;

-- ---- triggers ----
CREATE TRIGGER trg_conversation_participants_pair_key AFTER INSERT ON conversation_participants FOR EACH ROW EXECUTE FUNCTION trg_fn_conversation_participants_pair_key();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON conversation_participants FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON discard FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON groups FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON message_attachments FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON plans FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON recipe_ingredients FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON recipe_suggestions FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON recipes FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON requests FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON shopping_list_products FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON shopping_lists FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_stock_movements_apply AFTER INSERT ON stock_movements FOR EACH ROW EXECUTE FUNCTION trg_fn_stock_movements_apply();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON stock_products FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_stock_products_set_status BEFORE INSERT OR UPDATE OF expire_date ON stock_products FOR EACH ROW EXECUTE FUNCTION trg_fn_stock_products_set_status();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON stocks FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON subscriptions FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_log_transaction_status_change AFTER INSERT OR UPDATE ON transactions FOR EACH ROW EXECUTE FUNCTION fn_log_transaction_status_change();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON transactions FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON user_groups FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

COMMIT;
