import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Service d'envoi d'emails"""
    
    def __init__(self):
        self.enabled = Config.USE_EMAIL and Config.EMAIL_USER and Config.EMAIL_PASSWORD
        self.server = Config.EMAIL_SERVER
        self.port = Config.EMAIL_PORT
        self.sender = Config.EMAIL_USER
        self.password = Config.EMAIL_PASSWORD
        self.admin_email = Config.ADMIN_EMAIL
    
    def send_notification(self, courrier_id, objet, priorite):
        """
        Envoie une notification pour un nouveau courrier
        """
        if not self.enabled:
            logger.info(f"Email désactivé - Notification pour courrier #{courrier_id}: {objet}")
            return True
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = self.admin_email
            msg['Subject'] = f"[{priorite.upper()}] Nouveau courrier: {objet[:50]}"
            
            body = self._build_notification_body(courrier_id, objet, priorite)
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Connexion et envoi
            server = smtplib.SMTP(self.server, self.port)
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Notification envoyée pour courrier #{courrier_id}")
            return True
        
        except Exception as e:
            logger.error(f"Erreur envoi email: {e}")
            return False
    
    def _build_notification_body(self, courrier_id, objet, priorite):
        """
        Construit le corps du message
        """
        priority_labels = {
            'high': '🔴 URGENT',
            'medium': '🟡 Normal',
            'low': '🟢 Information'
        }
        
        priority_label = priority_labels.get(priorite, priorite)
        
        body = f"""
        📬 NOUVEAU COURRIER ENREGISTRÉ
        
        {priority_label}
        
        ID: {courrier_id}
        Objet: {objet}
        Date: {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        
        ---
        Connectez-vous à la plateforme pour plus de détails.
        
        Ministère de l'Aménagement du Territoire
        Système de Gestion des Courriers
        """
        
        return body
    
    def send_reminder(self, email, courriers_en_attente):
        """
        Envoie un rappel des courriers en attente
        """
        if not self.enabled:
            return True
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = email
            msg['Subject'] = f"Rappel: {courriers_en_attente} courrier(s) en attente"
            
            body = f"""
            Bonjour,
            
            Vous avez {courriers_en_attente} courrier(s) en attente de traitement.
            
            Veuillez vous connecter à la plateforme pour les traiter.
            
            Cordialement,
            Système de Gestion des Courriers
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.server, self.port)
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Rappel envoyé à {email}")
            return True
        
        except Exception as e:
            logger.error(f"Erreur envoi rappel: {e}")
            return False
    
    def test_connection(self):
        """
        Teste la connexion au serveur SMTP
        """
        if not self.enabled:
            return False, "Email désactivé dans la configuration"
        
        try:
            server = smtplib.SMTP(self.server, self.port)
            server.starttls()
            server.login(self.sender, self.password)
            server.quit()
            return True, "Connexion SMTP réussie"
        
        except Exception as e:
            return False, f"Erreur SMTP: {str(e)}"


# Import pour datetime
from datetime import datetime