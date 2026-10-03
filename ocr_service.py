import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
import os
from concurrent.futures import ThreadPoolExecutor
import time
import logging
from config import Config

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration de Tesseract
if os.path.exists(Config.TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_CMD
else:
    logger.warning(f"Tesseract non trouvé à {Config.TESSERACT_CMD}")


class OCRService:
    """Service d'OCR intelligent avec prétraitement d'images"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def preprocess_image(self, image_path):
        """
        Prétraitement avancé pour améliorer la qualité de l'OCR
        """
        try:
            # Chargement de l'image
            image = Image.open(image_path)
            
            # Conversion en niveaux de gris si nécessaire
            if image.mode != 'L':
                image = image.convert('L')
            
            # Amélioration du contraste
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Amélioration de la netteté
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)
            
            # Réduction du bruit
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # Binarisation adaptative (seuil automatique)
            threshold = self._calculate_optimal_threshold(image)
            image = image.point(lambda x: 0 if x < threshold else 255, '1')
            
            # Redimensionnement si trop petit
            min_width = 1000
            if image.width < min_width:
                ratio = min_width / image.width
                new_size = (int(image.width * ratio), int(image.height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            return image
        
        except Exception as e:
            logger.error(f"Erreur prétraitement image: {e}")
            return Image.open(image_path)
    
    def _calculate_optimal_threshold(self, image):
        """
        Calcule le seuil optimal pour la binarisation
        Méthode d'Otsu simplifiée
        """
        histogram = image.histogram()
        total_pixels = sum(histogram)
        
        best_threshold = 128
        best_variance = 0
        
        for threshold in range(1, 255):
            # Poids de la classe 1 (noir)
            weight1 = sum(histogram[:threshold])
            weight2 = total_pixels - weight1
            
            if weight1 == 0 or weight2 == 0:
                continue
            
            # Moyennes
            mean1 = sum(i * histogram[i] for i in range(threshold)) / weight1
            mean2 = sum(i * histogram[i] for i in range(threshold, 256)) / weight2
            
            # Variance inter-classe
            variance = weight1 * weight2 * (mean1 - mean2) ** 2 / (total_pixels ** 2)
            
            if variance > best_variance:
                best_variance = variance
                best_threshold = threshold
        
        return best_threshold
    
    def extract_text(self, image_path, lang='fra+eng'):
        """
        Extraction de texte avec Tesseract OCR
        """
        start_time = time.time()
        
        try:
            # Prétraitement
            processed_image = self.preprocess_image(image_path)
            
            # Configuration Tesseract
            custom_config = f'--oem 3 --psm 6 -l {lang}'
            
            # Extraction
            text = pytesseract.image_to_string(processed_image, config=custom_config)
            text = text.strip()
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Fallback si texte trop court
            if len(text) < 50:
                text = pytesseract.image_to_string(processed_image, config='--oem 3 --psm 6')
            
            confidence = self._calculate_confidence(text)
            
            logger.info(f"OCR terminé en {processing_time}ms, confiance: {confidence}%")
            
            return {
                'success': True,
                'text': text if text else "Aucun texte détecté. Vérifiez la qualité de l'image.",
                'processing_time_ms': processing_time,
                'confidence': confidence
            }
        
        except pytesseract.TesseractError as e:
            logger.error(f"Erreur Tesseract: {e}")
            return {
                'success': False,
                'error': f"Erreur OCR: {str(e)}",
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'confidence': 0
            }
        
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'confidence': 0
            }
    
    def extract_text_async(self, image_path, lang='fra+eng'):
        """
        Extraction OCR asynchrone
        """
        return self.executor.submit(self.extract_text, image_path, lang)
    
    def _calculate_confidence(self, text):
        """
        Calcule un score de confiance pour l'OCR
        """
        if not text:
            return 0
        
        confidence = 50  # Score de base
        
        # Critères de qualité
        word_count = len(text.split())
        if word_count > 100:
            confidence += 20
        elif word_count > 50:
            confidence += 15
        elif word_count > 20:
            confidence += 10
        
        # Présence de lettres et chiffres
        if re.search(r'[a-zA-Z]', text):
            confidence += 10
        if re.search(r'\d', text):
            confidence += 5
        
        # Longueur des mots
        words = text.split()
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            if avg_word_len > 4:
                confidence += 5
        
        # Ponctuation
        if re.search(r'[.!?,;:]', text):
            confidence += 5
        
        return min(95, confidence)
    
    def extract_courrier_info(self, text):
        """
        Extraction intelligente des informations du courrier
        """
        info = {
            'expediteur': None,
            'objet': None,
            'numero_reference': None,
            'date': None,
            'priorite': 'medium',
            'extras': {}
        }
        
        if not text:
            return info
        
        text_lower = text.lower()
        
        # ===== NUMERO DE REFERENCE =====
        # Format: 5 chiffres
        ref_match = re.search(r'\b(\d{5})\b', text)
        if ref_match:
            info['numero_reference'] = ref_match.group(1)
        
        # Format avec préfixe: REF-12345
        ref_match2 = re.search(r'(?:REF|N°|N|Numéro)[\s:]*(\d{5,10})', text, re.IGNORECASE)
        if ref_match2 and not info['numero_reference']:
            info['numero_reference'] = ref_match2.group(1)
        
        # ===== OBJET =====
        objet_patterns = [
            r'Objet\s*[:;]\s*(.+?)(?:\n|$)',
            r'OBJET\s*[:;]\s*(.+?)(?:\n|$)',
            r'Object\s*[:;]\s*(.+?)(?:\n|$)',
            r'RE:\s*(.+?)(?:\n|$)',
            r'Objet :\s*(.+?)(?:\n|$)'
        ]
        
        for pattern in objet_patterns:
            objet_match = re.search(pattern, text, re.IGNORECASE)
            if objet_match:
                objet_text = objet_match.group(1).strip()
                # Nettoyer l'objet
                objet_text = re.sub(r'\s+', ' ', objet_text)
                if len(objet_text) > 5:
                    info['objet'] = objet_text[:200]
                    break
        
        # ===== EXPEDITEUR =====
        expediteur_patterns = [
            r'(MINIST[EÈ]RE|AGENCE|DIRECTION|SERVICE|PRÉFECTURE|PROVINCE|COMMUNE|MAIRIE)[\s:]+([A-ZÀ-ÿ\s]+)',
            r'De\s*[:;]\s*(.+?)(?:\n|$)',
            r'Expéditeur\s*[:;]\s*(.+?)(?:\n|$)',
            r'(?:Envoyé par|Envoyé depuis)[\s:]+(.+?)(?:\n|$)'
        ]
        
        for pattern in expediteur_patterns:
            expediteur_match = re.search(pattern, text, re.IGNORECASE)
            if expediteur_match:
                expediteur_text = expediteur_match.group(0).strip()
                # Nettoyer
                expediteur_text = re.sub(r'\s+', ' ', expediteur_text)
                if len(expediteur_text) > 5 and len(expediteur_text) < 100:
                    info['expediteur'] = expediteur_text[:100]
                    break
        
        # Fallback: premier mot en majuscules suivi de texte
        if not info['expediteur']:
            lines = text.split('\n')
            for line in lines[:5]:
                if len(line) > 10 and line.upper() == line:
                    info['expediteur'] = line.strip()[:100]
                    break
        
        # ===== DATE =====
        date_patterns = [
            r'(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, text, re.IGNORECASE)
            if date_match:
                info['date'] = date_match.group(1)
                break
        
        # ===== PRIORITE =====
        urgent_keywords = ['urgent', 'important', 'alerte', 'prioritaire', 'asap', 'immédiat']
        low_keywords = ['information', 'note', 'rappel', 'circulation', 'bulletin']
        
        if any(kw in text_lower for kw in urgent_keywords):
            info['priorite'] = 'high'
        elif any(kw in text_lower for kw in low_keywords):
            info['priorite'] = 'low'
        
        # ===== INFORMATIONS EXTRAS =====
        # Détection de mots-clés importants
        important_keywords = ['COVID', 'PANDEMIE', 'URGENT SANITAIRE', 'DECISION MINISTERIELLE', 
                              'LOI', 'DECRET', 'ARRETE', 'CIRCULAIRE']
        
        found_keywords = [kw for kw in important_keywords if kw.lower() in text_lower]
        if found_keywords:
            info['extras']['keywords_found'] = found_keywords
        
        # Détection de destinataire
        dest_match = re.search(r'(?:À|A|Destinataire)[\s:]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if dest_match:
            info['extras']['destinataire'] = dest_match.group(1).strip()
        
        # Détection de copie
        cc_match = re.search(r'(?:CC|Copie)[\s:]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if cc_match:
            info['extras']['copie'] = cc_match.group(1).strip()
        
        return info
    
    def extract_qr_code(self, image_path):
        """
        Extraction de QR code (optionnel - nécessite pyzbar)
        """
        try:
            from pyzbar import pyzbar
            image = Image.open(image_path)
            qr_codes = pyzbar.decode(image)
            
            results = []
            for qr in qr_codes:
                results.append({
                    'type': qr.type,
                    'data': qr.data.decode('utf-8'),
                    'location': qr.rect
                })
            
            return results
        except ImportError:
            logger.warning("pyzbar non installé, extraction QR code désactivée")
            return []
        except Exception as e:
            logger.error(f"Erreur extraction QR code: {e}")
            return []