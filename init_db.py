import pymysql
from config import Config

def init_database():
    """Initialise la base de données sans utiliser la commande mysql"""
    
    # Connexion sans base de données spécifique
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        port=Config.DB_PORT,
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    # Créer la base de données si elle n'existe pas
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"✅ Base de données '{Config.DB_NAME}' créée ou existante")
    
    cursor.execute(f"USE {Config.DB_NAME}")
    
    # ========== CRÉATION DES TABLES ==========
    
    # Table roles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INT PRIMARY KEY AUTO_INCREMENT,
            nom VARCHAR(50) NOT NULL UNIQUE,
            niveau INT NOT NULL DEFAULT 1,
            description VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Table 'roles' créée")
    
    # Table users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(128) NOT NULL,
            nom_complet VARCHAR(100),
            email VARCHAR(100),
            telephone VARCHAR(20),
            departement VARCHAR(50),
            service VARCHAR(50),
            role_id INT NOT NULL,
            statut VARCHAR(20) DEFAULT 'actif',
            last_login DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT,
            INDEX idx_username (username),
            INDEX idx_email (email)
        )
    """)
    print("✅ Table 'users' créée")
    
    # Table courriers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courriers (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            numero_reference VARCHAR(50),
            date_reception DATE NOT NULL,
            expediteur VARCHAR(200) NOT NULL,
            email VARCHAR(100),
            objet VARCHAR(500) NOT NULL,
            contenu TEXT,
            priorite ENUM('low', 'medium', 'high') DEFAULT 'medium',
            statut ENUM('en_attente', 'traite', 'urgent', 'archive') DEFAULT 'en_attente',
            service_destinataire VARCHAR(50),
            scan_image_path VARCHAR(500),
            scan_image_name VARCHAR(255),
            scan_image_size INT,
            scan_image_type VARCHAR(10),
            original_filename VARCHAR(255),
            scan_score INT DEFAULT 0,
            scan_verdict VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_expediteur (expediteur),
            INDEX idx_objet (objet),
            INDEX idx_statut (statut),
            INDEX idx_created_at (created_at)
        )
    """)
    print("✅ Table 'courriers' créée")
    
    # Table audit_logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            action VARCHAR(50) NOT NULL,
            entity_type VARCHAR(50),
            entity_id INT,
            details TEXT,
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_created_at (created_at)
        )
    """)
    print("✅ Table 'audit_logs' créée")
    
    # Table scan_history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            filename VARCHAR(255),
            extracted_text TEXT,
            confidence_score INT,
            processing_time_ms INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_created_at (created_at)
        )
    """)
    print("✅ Table 'scan_history' créée")
    
    # Table notifications
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            title VARCHAR(200),
            message TEXT,
            type VARCHAR(50) DEFAULT 'info',
            is_read BOOLEAN DEFAULT FALSE,
            courrier_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (courrier_id) REFERENCES courriers(id) ON DELETE SET NULL,
            INDEX idx_is_read (is_read)
        )
    """)
    print("✅ Table 'notifications' créée")
    
    # Table attachments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id INT PRIMARY KEY AUTO_INCREMENT,
            courrier_id INT NOT NULL,
            filename VARCHAR(255) NOT NULL,
            filepath VARCHAR(500) NOT NULL,
            file_size INT,
            mime_type VARCHAR(100),
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (courrier_id) REFERENCES courriers(id) ON DELETE CASCADE
        )
    """)
    print("✅ Table 'attachments' créée")
    
    # ========== INSERTION DES DONNÉES INITIALES ==========
    
    # Insertion des rôles
    cursor.execute("""
        INSERT IGNORE INTO roles (id, nom, niveau, description) VALUES
        (1, 'stagiaire', 1, 'Accès limité - consultation uniquement'),
        (2, 'assistant', 3, 'Peut scanner et ajouter des courriers'),
        (3, 'charge_etude', 5, 'Peut modifier et exporter les courriers'),
        (4, 'chef_service', 8, 'Peut supprimer et archiver'),
        (5, 'directeur', 10, 'Accès total à toutes les fonctionnalités')
    """)
    print("✅ Rôles insérés")
    
    # Insertion des utilisateurs (avec mots de passe hashés - à mettre à jour via app.py plus tard)
    cursor.execute("""
        INSERT IGNORE INTO users (id, username, password_hash, nom_complet, email, telephone, role_id, service, statut) VALUES
        (1, 'ahmed.directeur', 'temp_hash', 'Ahmed Benali', 'ahmed@matn.gov.ma', '0612345678', 5, 'Direction Générale', 'actif'),
        (2, 'fatima.chef', 'temp_hash', 'Fatima Zahra', 'fatima@urbanisme.gov.ma', '0623456789', 4, 'Urbanisme', 'actif'),
        (3, 'karim.assistant', 'temp_hash', 'Karim Tazi', 'karim@habitat.gov.ma', '0634567890', 2, 'Habitat', 'actif'),
        (4, 'nadia.etude', 'temp_hash', 'Nadia El Fassi', 'nadia@amenagement.gov.ma', '0645678901', 3, 'Aménagement', 'actif'),
        (5, 'youssef.stagiaire', 'temp_hash', 'Youssef Meriem', 'youssef@matn.gov.ma', '0656789012', 1, 'Politique Ville', 'actif')
    """)
    print("✅ Utilisateurs insérés (hash temporaire - sera mis à jour par l'application)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("✅ BASE DE DONNÉES CRÉÉE AVEC SUCCÈS!")
    print("="*50)
    print("\n⚠️ IMPORTANT: Lancez ensuite 'python app.py' pour mettre à jour les mots de passe")

if __name__ == '__main__':
    init_database()