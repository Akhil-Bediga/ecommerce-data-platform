-- OLTP normalized (3NF) schema for benchmarking against the star schema.
-- Same logical data, normalized into 10 tables — represents what an upstream
-- transactional system would look like before warehouse modeling.

USE ecommerce;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS oltp_order_line;
DROP TABLE IF EXISTS oltp_order_header;
DROP TABLE IF EXISTS oltp_product;
DROP TABLE IF EXISTS oltp_subcategory;
DROP TABLE IF EXISTS oltp_category;
DROP TABLE IF EXISTS oltp_brand;
DROP TABLE IF EXISTS oltp_address;
DROP TABLE IF EXISTS oltp_customer;
DROP TABLE IF EXISTS oltp_segment;
DROP TABLE IF EXISTS oltp_store;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE oltp_segment (
  segment_id   TINYINT UNSIGNED PRIMARY KEY,
  segment_name VARCHAR(20) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE oltp_customer (
  customer_id   VARCHAR(36) PRIMARY KEY,
  first_name    VARCHAR(80),
  last_name     VARCHAR(80),
  email         VARCHAR(160),
  signup_date   DATE,
  segment_id    TINYINT UNSIGNED NOT NULL,
  KEY ix_oltp_cust_segment (segment_id),
  CONSTRAINT fk_oltp_cust_segment FOREIGN KEY (segment_id) REFERENCES oltp_segment(segment_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_address (
  address_id    INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  customer_id   VARCHAR(36) NOT NULL,
  country       VARCHAR(60),
  city          VARCHAR(80),
  KEY ix_oltp_addr_customer (customer_id),
  CONSTRAINT fk_oltp_addr_customer FOREIGN KEY (customer_id) REFERENCES oltp_customer(customer_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_category (
  category_id   TINYINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(80) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE oltp_subcategory (
  subcategory_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  category_id    TINYINT UNSIGNED NOT NULL,
  name           VARCHAR(80) NOT NULL,
  UNIQUE KEY uk_oltp_subcat (category_id, name),
  CONSTRAINT fk_oltp_subcat_cat FOREIGN KEY (category_id) REFERENCES oltp_category(category_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_brand (
  brand_id      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(80) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE oltp_product (
  product_id     VARCHAR(36) PRIMARY KEY,
  name           VARCHAR(160),
  brand_id       SMALLINT UNSIGNED,
  subcategory_id SMALLINT UNSIGNED,
  base_price     DECIMAL(10,2),
  KEY ix_oltp_prod_brand  (brand_id),
  KEY ix_oltp_prod_subcat (subcategory_id),
  CONSTRAINT fk_oltp_prod_brand  FOREIGN KEY (brand_id)       REFERENCES oltp_brand(brand_id),
  CONSTRAINT fk_oltp_prod_subcat FOREIGN KEY (subcategory_id) REFERENCES oltp_subcategory(subcategory_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_store (
  store_id      VARCHAR(36) PRIMARY KEY,
  name          VARCHAR(120),
  region        VARCHAR(60),
  country       VARCHAR(60),
  channel       ENUM('ONLINE','MOBILE','RETAIL'),
  KEY ix_oltp_store_channel (channel),
  KEY ix_oltp_store_region  (region)
) ENGINE=InnoDB;

CREATE TABLE oltp_order_header (
  order_id      VARCHAR(36) NOT NULL PRIMARY KEY,
  customer_id   VARCHAR(36) NOT NULL,
  store_id      VARCHAR(36) NOT NULL,
  order_date    DATE NOT NULL,
  order_status  ENUM('PLACED','SHIPPED','DELIVERED','RETURNED','CANCELLED') NOT NULL,
  KEY ix_oltp_orderhdr_customer (customer_id),
  KEY ix_oltp_orderhdr_store    (store_id),
  KEY ix_oltp_orderhdr_date     (order_date),
  CONSTRAINT fk_oltp_orderhdr_customer FOREIGN KEY (customer_id) REFERENCES oltp_customer(customer_id),
  CONSTRAINT fk_oltp_orderhdr_store    FOREIGN KEY (store_id)    REFERENCES oltp_store(store_id)
) ENGINE=InnoDB;

CREATE TABLE oltp_order_line (
  order_line_id   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_id        VARCHAR(36) NOT NULL,
  product_id      VARCHAR(36) NOT NULL,
  quantity        INT UNSIGNED NOT NULL,
  unit_price      DECIMAL(10,2) NOT NULL,
  discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  total_amount    DECIMAL(12,2) NOT NULL,
  KEY ix_oltp_orderline_order   (order_id),
  KEY ix_oltp_orderline_product (product_id),
  CONSTRAINT fk_oltp_orderline_order   FOREIGN KEY (order_id)   REFERENCES oltp_order_header(order_id),
  CONSTRAINT fk_oltp_orderline_product FOREIGN KEY (product_id) REFERENCES oltp_product(product_id)
) ENGINE=InnoDB;
