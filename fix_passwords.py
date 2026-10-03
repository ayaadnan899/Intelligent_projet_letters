import pymysql
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',  # Laissez vide si pas de mot de passe
    'database': 'courriers_db',
    'port': 3306
}

def fix_passwords():
    """Corrige les mots de passe des utilisateurs"""
    
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Liste des utilisateurs avec leurs vrais mots de passe
    users = [
        ('ahmed.directeur', 'directeur123'),
        ('fatima.chef', 'chef123'),
        ('karim.assistant', 'assistant123'),
        ('nadia.etude', 'etude123'),
        ('youssef.stagiaire', 'stagiaire123')
    ]
    
    print("=" * 50)
    print("🔐 MISE À JOUR DES MOTS DE PASSE")
    print("=" * 50)
    
    for username, plain_password in users:
        # Générer un vrai hash bcrypt
        new_hash = bcrypt.generate_password_hash(plain_password).decode('utf-8')
        
        # Mettre à jour dans la base
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE username = %s",
            (new_hash, username)
        )
        
        if cursor.rowcount > 0:
            print(f"✅ {username} -> mot de passe mis à jour")
        else:
            print(f"⚠️ {username} -> non trouvé")
    
    conn.commit()
    
    # Vérification
    print("\n" + "=" * 50)
    print("📋 VÉRIFICATION DES UTILISATEURS")
    print("=" * 50)
    
    cursor.execute("SELECT id, username, nom_complet, role_id FROM users")
    for user in cursor.fetchall():
        print(f"   ID:{user[0]} | {user[1]} | {user[2]} | role_id:{user[3]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ MOTS DE PASSE CORRIGÉS !")
    print("=" * 50)
    print("\n🔐 IDENTIFIANTS DE CONNEXION :")
    print("   ahmed.directeur / directeur123")
    print("   fatima.chef / chef123")
    print("   karim.assistant / assistant123")
    print("   nadia.etude / etude123")
    print("   youssef.stagiaire / stagiaire123")

if __name__ == '__main__':
    fix_passwords()