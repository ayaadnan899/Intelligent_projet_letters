import pymysql
from flask_bcrypt import Bcrypt
from datetime import datetime

bcrypt = Bcrypt()

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',  # Mettez votre mot de passe MySQL ici si vous en avez un
    'database': 'courriers_db',
    'port': 3306
}

def reset_complete():
    """Réinitialisation complète avec mots de passe valides"""
    
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("🗑️ SUPPRESSION DE L'ANCIENNE BASE...")
    print("=" * 60)
    
    # Supprimer l'ancienne base
    cursor.execute("DROP DATABASE IF EXISTS courriers_db")
    print("✅ Ancienne base supprimée")
    
    # Créer la nouvelle base
    cursor.execute("CREATE DATABASE courriers_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute("USE courriers_db")
    print("✅ Nouvelle base créée")
    
    # ========== CRÉATION DES TABLES ==========
    print("\n📋 CRÉATION DES TABLES...")
    
    # Table roles
    cursor.execute("""
        CREATE TABLE roles (
            id INT PRIMARY KEY AUTO_INCREMENT,
            nom VARCHAR(50) UNIQUE NOT NULL,
            niveau INT DEFAULT 1,
            description VARCHAR(200)
        )
    """)
    
    # Table users
    cursor.execute("""
        CREATE TABLE users (
            id INT PRIMARY KEY AUTO_INCREMENT,
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
        )
    """)
    
    # Table courriers
    cursor.execute("""
        CREATE TABLE courriers (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            numero_reference VARCHAR(50),
            date_reception DATE NOT NULL,
            expediteur VARCHAR(200) NOT NULL,
            email VARCHAR(100),
            objet VARCHAR(500) NOT NULL,
            contenu TEXT,
            priorite ENUM('low','medium','high') DEFAULT 'medium',
            statut ENUM('en_attente','traite','urgent','archive') DEFAULT 'en_attente',
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
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Table audit_logs
    cursor.execute("""
        CREATE TABLE audit_logs (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            action VARCHAR(50),
            entity_type VARCHAR(50),
            entity_id INT,
            details TEXT,
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Table scan_history
    cursor.execute("""
        CREATE TABLE scan_history (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            filename VARCHAR(255),
            extracted_text TEXT,
            confidence_score INT,
            processing_time_ms INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Table assignations
    cursor.execute("""
        CREATE TABLE assignations (
            id INT PRIMARY KEY AUTO_INCREMENT,
            courrier_id INT NOT NULL,
            assigned_to_user_id INT NOT NULL,
            assigned_by_user_id INT NOT NULL,
            service_destinataire VARCHAR(50),
            status ENUM('pending','accepted','rejected','completed') DEFAULT 'pending',
            commentaire TEXT,
            date_assignation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_traitement DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (courrier_id) REFERENCES courriers(id),
            FOREIGN KEY (assigned_to_user_id) REFERENCES users(id),
            FOREIGN KEY (assigned_by_user_id) REFERENCES users(id)
        )
    """)
    
    # Table notifications_assignation
    cursor.execute("""
        CREATE TABLE notifications_assignation (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            courrier_id INT NOT NULL,
            message TEXT,
            type VARCHAR(50) DEFAULT 'assignation',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (courrier_id) REFERENCES courriers(id)
        )
    """)
    
    print("✅ Toutes les tables créées")
    
    # ========== INSERTION DES RÔLES ==========
    print("\n📋 INSERTION DES RÔLES...")
    cursor.execute("""
        INSERT INTO roles (id, nom, niveau, description) VALUES
        (1, 'stagiaire', 1, 'Consultation uniquement'),
        (2, 'assistant', 3, 'Ajout des courriers'),
        (3, 'charge_etude', 5, 'Modification des courriers'),
        (4, 'chef_service', 8, 'Gestion des courriers'),
        (5, 'directeur', 10, 'Accès total')
    """)
    print("✅ 5 rôles insérés")
    
    # ========== INSERTION DES UTILISATEURS AVEC VRAIS HASH ==========
    print("\n📋 INSERTION DES UTILISATEURS...")
    
    users_data = [
        (1, 'ahmed.directeur', 'directeur123', 'Ahmed Benali', 'ahmed.directeur@matn.gov.ma', '0612345678', 'Direction Générale', 'Direction Générale', 5),
        (2, 'fatima.chef', 'chef123', 'Fatima Zahra', 'fatima.chef@urbanisme.gov.ma', '0623456789', 'Urbanisme', 'Urbanisme', 4),
        (3, 'karim.assistant', 'assistant123', 'Karim Tazi', 'karim.assistant@habitat.gov.ma', '0634567890', 'Habitat', 'Habitat', 2),
        (4, 'nadia.etude', 'etude123', 'Nadia El Fassi', 'nadia.etude@amenagement.gov.ma', '0645678901', 'Aménagement', 'Aménagement', 3),
        (5, 'youssef.stagiaire', 'stagiaire123', 'Youssef Meriem', 'youssef.stagiaire@politiqueville.gov.ma', '0656789012', 'Politique Ville', 'Politique Ville', 1)
    ]
    
    for user in users_data:
        password_hash = bcrypt.generate_password_hash(user[2]).decode('utf-8')
        cursor.execute("""
            INSERT INTO users (id, username, password_hash, nom_complet, email, telephone, departement, service, role_id, statut)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'actif')
        """, (user[0], user[1], password_hash, user[3], user[4], user[5], user[6], user[7], user[8]))
        print(f"   ✅ {user[1]} / {user[2]}")
    
    # ========== INSERTION DES COURRIERS ==========
    print("\n📋 INSERTION DES COURRIERS DE TEST...")
    
    courriers_data = [
        (1, 1, 'REF-URG-001', '2026-05-10', 'Ministère de l\'Intérieur', 'contact@interieur.gov.ma', 
         'URGENT - Crise sécuritaire', 'Coordination urgente pour la gestion de crise.', 'high', 'urgent', 'Direction Générale'),
        (2, 2, 'REF-URG-002', '2026-05-11', 'Préfecture de Casablanca', 'prefecture@casablanca.ma', 
         'URGENT - Inondations', 'Intervention urgente requise.', 'high', 'urgent', 'Urbanisme'),
        (3, 3, 'REF-ATT-001', '2026-05-12', 'Agence Urbaine', 'contact@agence.ma', 
         'Permis de construire', 'Demande de permis pour projet résidentiel.', 'high', 'en_attente', 'Urbanisme'),
        (4, 4, 'REF-ATT-002', '2026-05-13', 'Office National de l\'Eau', 'contact@one.ma', 
         'Raccordement eau', 'Demande de raccordement réseau.', 'medium', 'en_attente', 'Aménagement'),
        (5, 5, 'REF-TRT-001', '2026-05-05', 'Ministère des Finances', 'finance@finances.gov.ma', 
         'Budget 2026', 'Notification budgétaire.', 'medium', 'traite', 'Direction Générale')
    ]
    
    for c in courriers_data:
        cursor.execute("""
            INSERT INTO courriers (id, user_id, numero_reference, date_reception, expediteur, email, objet, contenu, priorite, statut, service_destinataire)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, c)
    
    print("✅ 5 courriers de test insérés")
    
    # ========== INSERTION DES ASSIGNATIONS ==========
    print("\n📋 INSERTION DES ASSIGNATIONS...")
    
    cursor.execute("""
        INSERT INTO assignations (courrier_id, assigned_to_user_id, assigned_by_user_id, service_destinataire, status, commentaire)
        VALUES 
        (3, 2, 1, 'Urbanisme', 'pending', 'Urgent - Traiter ce permis rapidement'),
        (4, 4, 1, 'Aménagement', 'pending', 'Coordonner avec le service technique'),
        (1, 1, 1, 'Direction Générale', 'pending', 'Préparer rapport pour le ministre')
    """)
    print("✅ 3 assignations insérées")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ BASE DE DONNÉES RÉINITIALISÉE AVEC SUCCÈS !")
    print("=" * 60)
    print("\n🔐 IDENTIFIANTS DE CONNEXION VALIDES :")
    print("   ┌─────────────────────────┬─────────────────┐")
    print("   │ Utilisateur             │ Mot de passe    │")
    print("   ├─────────────────────────┼─────────────────┤")
    print("   │ ahmed.directeur         │ directeur123    │")
    print("   │ fatima.chef             │ chef123         │")
    print("   │ karim.assistant         │ assistant123    │")
    print("   │ nadia.etude             │ etude123        │")
    print("   │ youssef.stagiaire       │ stagiaire123    │")
    print("   └─────────────────────────┴─────────────────┘")
    print("\n🚀 Lancez maintenant : python app.py")
    print("🌐 http://localhost:5000")
    print("=" * 60)

if __name__ == '__main__':
    reset_complete()