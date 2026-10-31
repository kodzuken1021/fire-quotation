-- Fire Protection Quotation and Inspection Request System
-- Works on XAMPP MariaDB / MySQL. Safe to run more than once.
-- PowerShell:  C:\xampp\mysql\bin\mysql.exe -u root < database\schema.sql

CREATE DATABASE IF NOT EXISTS fire_quotation
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE fire_quotation;

-- Users: clients register on the website; admins are created with `flask create-admin`
CREATE TABLE IF NOT EXISTS users (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  full_name      VARCHAR(100) NOT NULL,
  email          VARCHAR(120) NOT NULL UNIQUE,
  password_hash  VARCHAR(255) NOT NULL,
  role           ENUM('client','admin') NOT NULL DEFAULT 'client',
  company_name   VARCHAR(120) NULL,
  contact_number VARCHAR(30)  NULL,
  profile_photo  VARCHAR(255) NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Catalog shown to visitors (no prices). is_active = 0 hides an item instead of deleting it.
CREATE TABLE IF NOT EXISTS catalog_items (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(150) NOT NULL,
  category    ENUM('Extinguisher','FDAS','Suppression System','Service') NOT NULL,
  description TEXT NULL,
  is_active   TINYINT(1) NOT NULL DEFAULT 1,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_item_name_category (name, category)
) ENGINE=InnoDB;

-- One quote request per submission by a client.
-- inspection_date is the date the admin confirms (date only, no time).
CREATE TABLE IF NOT EXISTS quote_requests (
  id                         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id                    INT UNSIGNED NOT NULL,
  status                     ENUM('Pending','Inspection Scheduled','Quote Sent','Cancelled')
                             NOT NULL DEFAULT 'Pending',
  needs_installation         TINYINT(1) NOT NULL DEFAULT 0,
  needs_testing              TINYINT(1) NOT NULL DEFAULT 0,
  wants_inspection           TINYINT(1) NOT NULL DEFAULT 0,
  inspection_address         VARCHAR(255) NULL,
  preferred_inspection_date  DATE NULL,
  inspection_date            DATE NULL,
  notes                      TEXT NULL,
  created_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_qr_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Items the client selected on the request form
CREATE TABLE IF NOT EXISTS quote_request_items (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  request_id INT UNSIGNED NOT NULL,
  item_id    INT UNSIGNED NOT NULL,
  quantity   INT UNSIGNED NOT NULL DEFAULT 1,
  CONSTRAINT chk_qri_qty CHECK (quantity >= 1),
  CONSTRAINT fk_qri_request FOREIGN KEY (request_id) REFERENCES quote_requests(id) ON DELETE CASCADE,
  CONSTRAINT fk_qri_item FOREIGN KEY (item_id) REFERENCES catalog_items(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Official quotation prepared by the admin (at most one per request)
CREATE TABLE IF NOT EXISTS quotations (
  id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  request_id          INT UNSIGNED NOT NULL UNIQUE,
  quotation_no        VARCHAR(30) NOT NULL UNIQUE,
  installation_charge DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  testing_charge      DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  total_amount        DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  valid_until         DATE NULL,
  pdf_path            VARCHAR(255) NULL,
  sent_at             DATETIME NULL,
  created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_q_amounts CHECK (installation_charge >= 0 AND testing_charge >= 0 AND total_amount >= 0),
  CONSTRAINT fk_q_request FOREIGN KEY (request_id) REFERENCES quote_requests(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Priced line items of a quotation
CREATE TABLE IF NOT EXISTS quotation_items (
  id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  quotation_id INT UNSIGNED NOT NULL,
  item_id      INT UNSIGNED NOT NULL,
  quantity     INT UNSIGNED NOT NULL,
  unit_price   DECIMAL(12,2) NOT NULL,
  line_total   DECIMAL(12,2) NOT NULL,
  CONSTRAINT chk_qi_values CHECK (quantity >= 1 AND unit_price >= 0 AND line_total >= 0),
  CONSTRAINT fk_qi_quotation FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE,
  CONSTRAINT fk_qi_item FOREIGN KEY (item_id) REFERENCES catalog_items(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Catalog data. INSERT IGNORE + the unique key means re-running this file never creates duplicates.
INSERT IGNORE INTO catalog_items (name, category, description) VALUES
 ('Dry Chemical (ABC) Extinguisher - 2.2 lbs / 1 kg', 'Extinguisher', 'Compact option for suitable applications and limited spaces.'),
 ('Dry Chemical (ABC) Extinguisher - 5 lbs / 2.3 kg', 'Extinguisher', 'Suitable for light motor vehicles and other appropriate applications.'),
 ('Dry Chemical (ABC) Extinguisher - 10 lbs / 4.5 kg', 'Extinguisher', 'For homes and various commercial applications.'),
 ('Dry Chemical (ABC) Extinguisher - 20 lbs / 9.1 kg', 'Extinguisher', 'For applications requiring greater extinguishing capacity.'),
 ('Dry Chemical (ABC) Extinguisher - 50 lbs (Wheeled)', 'Extinguisher', 'Wheeled unit for larger fire risks and greater extinguishing capacity.'),
 ('Foam Type (AFFF) Extinguisher - 20 lbs / 9.1 kg', 'Extinguisher', 'Suitable for specific applications involving flammable liquids and other compatible fire risks.'),
 ('Foam Type (AFFF) Extinguisher - 50 lbs (Wheeled)', 'Extinguisher', 'A wheeled foam extinguisher designed for larger fire risks involving compatible flammable liquids and other suitable applications.'),
 ('Kitchen Hood Fire Suppression System', 'Suppression System', 'Fire protection designed for commercial kitchens. Protect your cooking equipment, kitchen hood, and surrounding areas with a professionally designed kitchen hood suppression system.');

INSERT IGNORE INTO catalog_items (name, category, description, is_active) VALUES
 ('Conventional FDAS', 'FDAS', 'Zone-based fire detection and alarm system for small to mid-size buildings.', 1),
 ('Addressable FDAS', 'FDAS', 'Every device reports its own address, so you see exactly where an alarm started.', 1),
 ('Semi-Addressable FDAS', 'FDAS', 'Mix of zone-based and addressable devices for mid-size sites.', 1),
 ('Smoke Detector', 'FDAS', 'Detects smoke particles early.', 1),
 ('Heat Detector', 'FDAS', 'Detects a rise in temperature; suited to kitchens and dusty areas.', 1),
 ('Beam Detector', 'FDAS', 'Detects smoke across large open spaces such as warehouses.', 1),
 ('Strobe Horn', 'FDAS', 'Audible and visual alarm notification device.', 1),
 ('Mechanical Bell', 'FDAS', 'Loud audible alarm bell.', 1),
 ('Manual Call Point', 'FDAS', 'Break-glass station to trigger the alarm by hand.', 1);

INSERT IGNORE INTO catalog_items (name, category, description) VALUES
 ('Fire Extinguisher Inspection', 'Service', 'On-site inspection of extinguishers.'),
 ('Fire Extinguisher Maintenance and Refilling', 'Service', 'Servicing, refilling and recharging of extinguishers.'),
 ('Fire Alarm System Maintenance', 'Service', 'Periodic testing and maintenance of fire alarm systems.');