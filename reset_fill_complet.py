import pymysql
from flask_bcrypt import Bcrypt
from datetime import datetime

bcrypt = Bcrypt()

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',  # Mettez votre mot de passe
    'database': 'courriers_db',
    'port': 3306
}

def reset_and_fill():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Vider les tables
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute("TRUNCATE TABLE assignations")
    cursor.execute("TRUNCATE TABLE notifications_assignation")
    cursor.execute("TRUNCATE TABLE audit_logs")
    cursor.execute("TRUNCATE TABLE scan_history")
    cursor.execute("TRUNCATE TABLE courriers")
    cursor.execute("TRUNCATE TABLE users")
    cursor.execute("TRUNCATE TABLE roles")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("🗑️ Tables vidées")
    
    # Recréer les rôles
    cursor.execute("""
        INSERT INTO roles (id, nom, niveau, description) VALUES
        (1, 'stagiaire', 1, 'Consultation uniquement'),
        (2, 'assistant', 3, 'Ajout de courriers'),
        (3, 'charge_etude', 5, 'Modification'),
        (4, 'chef_service', 8, 'Gestion'),
        (5, 'directeur', 10, 'Accès total')
    """)
    print("✅ Rôles créés")
    
    # Créer les utilisateurs avec mots de passe hashés
    users = [
        (1, 'ahmed.directeur', 'directeur123', 'Ahmed Benali', 'ahmed@matn.gov.ma', 'Direction Générale', 5),
        (2, 'fatima.chef', 'chef123', 'Fatima Zahra', 'fatima@urbanisme.gov.ma', 'Urbanisme', 4),
        (3, 'karim.assistant', 'assistant123', 'Karim Tazi', 'karim@habitat.gov.ma', 'Habitat', 2),
        (4, 'nadia.etude', 'etude123', 'Nadia El Fassi', 'nadia@amenagement.gov.ma', 'Aménagement', 3),
        (5, 'youssef.stagiaire', 'stagiaire123', 'Youssef Meriem', 'youssef@matn.gov.ma', 'Politique Ville', 1)
    ]
    
    for user in users:
        password_hash = bcrypt.generate_password_hash(user[2]).decode('utf-8')
        cursor.execute("""
            INSERT INTO users (id, username, password_hash, nom_complet, email, service, role_id, statut)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'actif')
        """, (user[0], user[1], password_hash, user[3], user[4], user[5], user[6]))
    print("✅ 5 utilisateurs créés")
    
    # Créer des courriers
    cursor.execute("""
        INSERT INTO courriers (user_id, numero_reference, date_reception, expediteur, objet, contenu, priorite, statut, service_destinataire) VALUES
        (1, 'REF-001', CURDATE(), 'Ministère de l\'Intérieur', 'URGENT - Crise sécuritaire', 'Coordination urgente requise', 'high', 'urgent', 'Direction Générale'),
        (2, 'REF-002', CURDATE(), 'Agence Urbaine', 'Permis de construire - Zone industrielle', 'Demande de permis pour projet', 'high', 'en_attente', 'Urbanisme'),
        (3, 'REF-003', CURDATE(), 'Préfecture', 'Programme logements sociaux', 'Projet habitat social', 'medium', 'en_attente', 'Habitat'),
        (4, 'REF-004', CURDATE(), 'ONE', 'Raccordement réseau eau', 'Demande technique', 'medium', 'en_attente', 'Aménagement'),
        (5, 'REF-005', CURDATE(), 'Ministère des Finances', 'Budget 2026', 'Notification budgétaire', 'high', 'traite', 'Direction Générale')
    """)
    print("✅ 5 courriers créés")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("✅ BASE DE DONNÉES RÉINITIALISÉE!")
    print("="*50)
    print("\n🔐 COMPTES DE TEST:")
    print("   ahmed.directeur / directeur123")
    print("   fatima.chef / chef123")
    print("   karim.assistant / assistant123")
    print("   nadia.etude / etude123")
    print("   youssef.stagiaire / stagiaire123")
    print("\n🚀 Relancez: python app.py")

if __name__ == '__main__':
    reset_and_fill()