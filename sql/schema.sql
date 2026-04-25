-- E-Commerce Data Platform: Star Schema DDL
-- Grain of fact_order_items: one row per order line (order_id × product_id)

CREATE DATABASE IF NOT EXISTS ecommerce
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecommerce;

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_store;

CREATE TABLE dim_customer (
  customer_key   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  customer_id    VARCHAR(36)  NOT NULL,
  first_name     VARCHAR(80),
  last_name      VARCHAR(80),
  email          VARCHAR(160),
  country        VARCHAR(60),
  city           VARCHAR(80),
  signup_date    DATE,
  segment        ENUM('NEW', 'REGULAR', 'VIP') NOT NULL DEFAULT 'NEW',
  PRIMARY KEY (customer_key),
  UNIQUE KEY uk_customer_id (customer_id),
  KEY ix_customer_country (country),
  KEY ix_customer_segment (segment)
) ENGINE=InnoDB;

CREATE TABLE dim_product (
  product_key    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id     VARCHAR(36)  NOT NULL,
  name           VARCHAR(160) NOT NULL,
  category       VARCHAR(80),
  subcategory    VARCHAR(80),
  brand          VARCHAR(80),
  base_price     DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (product_key),
  UNIQUE KEY uk_product_id (product_id),
  KEY ix_product_category (category, subcategory),
  KEY ix_product_brand (brand)
) ENGINE=InnoDB;

CREATE TABLE dim_date (
  date_key      INT UNSIGNED NOT NULL,           -- YYYYMMDD
  full_date     DATE NOT NULL,
  day           TINYINT UNSIGNED NOT NULL,
  month         TINYINT UNSIGNED NOT NULL,
  quarter       TINYINT UNSIGNED NOT NULL,
  year          SMALLINT UNSIGNED NOT NULL,
  day_of_week   TINYINT UNSIGNED NOT NULL,        -- 1=Mon..7=Sun
  is_weekend    TINYINT(1)       NOT NULL,
  PRIMARY KEY (date_key),
  UNIQUE KEY uk_full_date (full_date),
  KEY ix_year_month (year, month)
) ENGINE=InnoDB;

CREATE TABLE dim_store (
  store_key     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  store_id      VARCHAR(36)  NOT NULL,
  name          VARCHAR(120) NOT NULL,
  region        VARCHAR(60),
  country       VARCHAR(60),
  channel       ENUM('ONLINE','MOBILE','RETAIL') NOT NULL,
  PRIMARY KEY (store_key),
  UNIQUE KEY uk_store_id (store_id),
  KEY ix_store_channel (channel),
  KEY ix_store_region (region)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Fact
-- ---------------------------------------------------------------------------

CREATE TABLE fact_order_items (
  order_item_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          VARCHAR(36)     NOT NULL,
  customer_key      INT UNSIGNED    NOT NULL,
  product_key       INT UNSIGNED    NOT NULL,
  date_key          INT UNSIGNED    NOT NULL,
  store_key         INT UNSIGNED    NOT NULL,
  quantity          INT UNSIGNED    NOT NULL,
  unit_price        DECIMAL(10,2)   NOT NULL,
  discount_amount   DECIMAL(10,2)   NOT NULL DEFAULT 0,
  total_amount      DECIMAL(12,2)   NOT NULL,
  order_status      ENUM('PLACED','SHIPPED','DELIVERED','RETURNED','CANCELLED') NOT NULL,
  created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (order_item_id),
  KEY ix_fact_order_id   (order_id),
  KEY ix_fact_customer   (customer_key),
  KEY ix_fact_product    (product_key),
  KEY ix_fact_date       (date_key),
  KEY ix_fact_store      (store_key),
  KEY ix_fact_status     (order_status),
  CONSTRAINT fk_fact_customer FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
  CONSTRAINT fk_fact_product  FOREIGN KEY (product_key)  REFERENCES dim_product(product_key),
  CONSTRAINT fk_fact_date     FOREIGN KEY (date_key)     REFERENCES dim_date(date_key),
  CONSTRAINT fk_fact_store    FOREIGN KEY (store_key)    REFERENCES dim_store(store_key)
) ENGINE=InnoDB;
