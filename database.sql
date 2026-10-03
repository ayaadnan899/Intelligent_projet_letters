-- =====================================================
-- BASE DE DONNÉES SIMPLE ET STABLE
-- GESTION INTELLIGENTE DES COURRIERS
-- =====================================================

DROP DATABASE IF EXISTS courriers_db;

CREATE DATABASE courriers_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE courriers_db;

-- =====================================================
-- TABLE ROLES
-- =====================================================

CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(50) UNIQUE NOT NULL,
    niveau INT DEFAULT 1,
    description VARCHAR(200)
);

INSERT INTO roles (id, nom, niveau, description) VALUES
(1, 'stagiaire', 1, 'Consultation uniquement'),
(2, 'assistant', 3, 'Ajout des courriers'),
(3, 'charge_etude', 5, 'Modification des courriers'),
(4, 'chef_service', 8, 'Gestion des courriers'),
(5, 'directeur', 10, 'Accès total');

-- =====================================================
-- TABLE USERS (5 UTILISATEURS SEULEMENT)
-- =====================================================

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    nom_complet VARCHAR(100),
    email VARCHAR(100),
    telephone VARCHAR(20),
    departement VARCHAR(50),
    service VARCHAR(50),
    role_id INT,
    statut VARCHAR(20) DEFAULT 'actif',
    last_login DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (role_id) REFERENCES roles(id)
);

-- Insertion des 5 utilisateurs (mots de passe temporaires)
INSERT INTO users (id, username, password_hash, nom_complet, email, telephone, departement, service, role_id) VALUES
(1, 'ahmed.directeur', 'temp_hash', 'Ahmed Benali', 'ahmed@matn.gov.ma', '0612345678', 'Direction Générale', 'Direction Générale', 5),
(2, 'fatima.chef', 'temp_hash', 'Fatima Zahra', 'fatima@urbanisme.gov.ma', '0623456789', 'Urbanisme', 'Urbanisme', 4),
(3, 'karim.assistant', 'temp_hash', 'Karim Tazi', 'karim@habitat.gov.ma', '0634567890', 'Habitat', 'Habitat', 2),
(4, 'nadia.etude', 'temp_hash', 'Nadia El Fassi', 'nadia@amenagement.gov.ma', '0645678901', 'Aménagement', 'Aménagement', 3),
(5, 'youssef.stagiaire', 'temp_hash', 'Youssef Meriem', 'youssef@matn.gov.ma', '0656789012', 'Politique Ville', 'Politique Ville', 1);

-- =====================================================
-- TABLE COURRIERS
-- =====================================================

CREATE TABLE courriers (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    numero_reference VARCHAR(50),

    date_reception DATE NOT NULL,

    expediteur VARCHAR(200) NOT NULL,

    email VARCHAR(100),

    objet VARCHAR(500) NOT NULL,

    contenu TEXT,

    priorite ENUM('low','medium','high') DEFAULT 'medium',

    statut ENUM('en_attente','traite','urgent','archive')
    DEFAULT 'en_attente',

    service_destinataire VARCHAR(50),

    scan_image_path VARCHAR(500),
    scan_image_name VARCHAR(255),
    scan_image_size INT,
    scan_image_type VARCHAR(10),
    original_filename VARCHAR(255),

    scan_score INT DEFAULT 0,
    scan_verdict VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- =====================================================
-- INSERT COURRIERS TEST
-- =====================================================

INSERT INTO courriers (
    user_id,
    numero_reference,
    date_reception,
    expediteur,
    email,
    objet,
    contenu,
    priorite,
    statut,
    service_destinataire
) VALUES

(
1,
'REF-001',
'2026-05-01',
'Ministère de l''Intérieur',
'contact@interieur.gov.ma',
'Demande de coordination',
'Courrier officiel de coordination.',
'high',
'urgent',
'Direction Générale'
),

(
2,
'REF-002',
'2026-05-02',
'Agence Urbaine',
'contact@agence.ma',
'Projet urbanisme',
'Dossier urbanistique.',
'medium',
'en_attente',
'Urbanisme'
),

(
3,
'REF-003',
'2026-05-03',
'Préfecture',
'prefecture@rabat.ma',
'Programme habitat',
'Projet habitat social.',
'low',
'traite',
'Habitat'
),

(
4,
'REF-004',
'2026-05-04',
'Ministère des Finances',
'finance@finances.gov.ma',
'Budget 2026',
'Notification budgétaire.',
'high',
'en_attente',
'Aménagement'
),

(
5,
'REF-005',
'2026-05-05',
'Université Internationale',
'contact@ui.ma',
'Convention partenariat',
'Proposition de convention.',
'medium',
'en_attente',
'Politique Ville'
);

-- =====================================================
-- TABLE AUDIT LOGS
-- =====================================================

CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    action VARCHAR(50),

    entity_type VARCHAR(50),

    entity_id INT,

    details TEXT,

    ip_address VARCHAR(45),

    user_agent VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- =====================================================
-- TABLE SCAN HISTORY
-- =====================================================

CREATE TABLE scan_history (
    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL,

    filename VARCHAR(255),

    extracted_text TEXT,

    confidence_score INT,

    processing_time_ms INT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- =====================================================
-- INDEX SIMPLES
-- =====================================================

CREATE INDEX idx_username ON users(username);
CREATE INDEX idx_email ON users(email);
CREATE INDEX idx_courrier_objet ON courriers(objet(100));
CREATE INDEX idx_courrier_expediteur ON courriers(expediteur(100));
CREATE INDEX idx_courrier_statut ON courriers(statut);
CREATE INDEX idx_courrier_user ON courriers(user_id);

-- =====================================================
-- MESSAGE FINAL
-- =====================================================

SELECT 'BASE DE DONNÉES CRÉÉE AVEC SUCCÈS' AS STATUS;
SELECT '5 UTILISATEURS AJOUTÉS' AS INFO;
SELECT * FROM users;
SELECT * FROM roles;