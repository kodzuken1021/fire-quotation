-- Fire Protection Quotation and Inspection Request System
-- Works on XAMPP MariaDB / MySQL. Run the whole file once.
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
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- One quote request per submission by a client
CREATE TABLE IF NOT EXISTS quote_requests (
  id                 INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id            INT UNSIGNED NOT NULL,
  status             ENUM('Pending','Inspection Scheduled','Quote Sent','Cancelled')
                     NOT NULL DEFAULT 'Pending',
  needs_installation TINYINT(1) NOT NULL DEFAULT 0,
  needs_testing      TINYINT(1) NOT NULL DEFAULT 0,
  wants_inspection   TINYINT(1) NOT NULL DEFAULT 0,
  notes              TEXT NULL,
  created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
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

-- Free on-site inspection, scheduled by the admin (at most one per request)
CREATE TABLE IF NOT EXISTS inspections (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  request_id     INT UNSIGNED NOT NULL UNIQUE,
  scheduled_date DATETIME NOT NULL,
  status         ENUM('Scheduled','Completed','Cancelled') NOT NULL DEFAULT 'Scheduled',
  notes          TEXT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_insp_request FOREIGN KEY (request_id) REFERENCES quote_requests(id) ON DELETE CASCADE
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

-- Catalog data. Extinguisher types and the kitchen hood system come from the client's product list.
-- The FDAS and Service rows are still SAMPLES: replace them with the client's real offerings.
INSERT INTO catalog_items (name, category, description) VALUES
 ('Dry Chemical (ABC) Extinguisher - 2.2 lbs / 1 kg', 'Extinguisher', 'Compact option for suitable applications and limited spaces.'),
 ('Dry Chemical (ABC) Extinguisher - 5 lbs / 2.3 kg', 'Extinguisher', 'Suitable for light motor vehicles and other appropriate applications.'),
 ('Dry Chemical (ABC) Extinguisher - 10 lbs / 4.5 kg', 'Extinguisher', 'For homes and various commercial applications.'),
 ('Dry Chemical (ABC) Extinguisher - 20 lbs / 9.1 kg', 'Extinguisher', 'For applications requiring greater extinguishing capacity.'),
 ('Dry Chemical (ABC) Extinguisher - 50 lbs (Wheeled)', 'Extinguisher', 'Wheeled unit for larger fire risks and greater extinguishing capacity.'),
 ('Foam Type (AFFF) Extinguisher - 20 lbs / 9.1 kg', 'Extinguisher', 'Suitable for specific applications involving flammable liquids and other compatible fire risks.'),
 ('Foam Type (AFFF) Extinguisher - 50 lbs (Wheeled)', 'Extinguisher', 'A wheeled foam extinguisher designed for larger fire risks involving compatible flammable liquids and other suitable applications.'),
 ('Kitchen Hood Fire Suppression System', 'Suppression System', 'Fire protection designed for commercial kitchens. Protect your cooking equipment, kitchen hood, and surrounding areas with a professionally designed kitchen hood suppression system.'),
 ('Conventional Fire Detection and Alarm System (FDAS)', 'FDAS', 'Zone-based detection and alarm system for small to medium buildings.'),
 ('Addressable Fire Detection and Alarm System (FDAS)', 'FDAS', 'Device-level detection and alarm system for larger buildings.'),
 ('Fire Extinguisher Inspection', 'Service', 'On-site inspection of extinguishers.'),
 ('Fire Extinguisher Maintenance and Refilling', 'Service', 'Servicing, refilling and recharging of extinguishers.'),
 ('Fire Alarm System Maintenance', 'Service', 'Periodic testing and maintenance of fire alarm systems.');