import cv2
import numpy as np
from config.logging_config import logger
from services.ocr.image_utils import ImageUtils

class ImagePreprocessor:
    """Preprocesses low-quality mobile uploads and scanned documents for high-accuracy OCR."""
    
    @staticmethod
    def read_image(image_path: str) -> np.ndarray:
        """Safely loads an image file from a path."""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Could not load image at path: {image_path}")
        return img

    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """Converts colored BGR image to grayscale."""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    @staticmethod
    def reduce_noise(image: np.ndarray) -> np.ndarray:
        """Applies bilateral filtering to remove creases/wrinkles while maintaining sharp text edges."""
        # Bilateral filter keeps edges sharp compared to Gaussian blur
        return cv2.bilateralFilter(image, 9, 75, 75)

    @staticmethod
    def adaptive_binarize(image: np.ndarray) -> np.ndarray:
        """Converts grayscale image to high-contrast black & white to enhance low-quality print."""
        # Clean background illumination variations
        return cv2.adaptiveThreshold(
            image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

    @staticmethod
    def de_skew(image: np.ndarray) -> np.ndarray:
        """Detects image skew angle and rotates the image to prevent slanted OCR lines."""
        try:
            # Threshold the image
            _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find all coordinates of foreground text pixels
            coords = np.column_stack(np.where(thresh > 0))
            
            if len(coords) < 10:
                return image
            
            # Compute a bounding box containing all text points
            angle = cv2.minAreaRect(coords)[-1]
            
            # minAreaRect returns angle in [-90, 0)
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
                
            # Perform rotation if skew is significant (> 0.5 degrees and < 45 degrees)
            if 0.5 < abs(angle) < 45:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                )
                logger.info(f"De-skewed image by rotating {angle:.2f} degrees.")
                return rotated
        except Exception as e:
            logger.warning(f"De-skewing process skipped or failed: {str(e)}")
            
        return image

    @classmethod
    def preprocess(cls, image_path: str, save_path: str = None) -> np.ndarray:
        """
        Executes complete cleanup pipeline:
        Load -> Perspective Correct -> Resolution Normalize -> Grayscale ->
        CLAHE Contrast -> Denoise -> De-skew -> Sharpen -> Binarize.
        
        Saves preprocessed image to save_path if specified.
        """
        logger.info(f"Preprocessing image file: {image_path}")
        
        # 1. Load image
        img = cls.read_image(image_path)
        
        # 2. Perspective correction (mobile camera angle shots)
        img = ImageUtils.correct_perspective(img)
        
        # 3. Resolution normalization (standardize to 300 DPI equivalent)
        img = ImageUtils.normalize_resolution(img, target_dpi=300, current_dpi=72)
        
        # 4. Convert to grayscale
        gray = cls.to_grayscale(img)
        
        # 5. CLAHE contrast enhancement (faded text, poor lighting)
        enhanced = ImageUtils.enhance_contrast_clahe(gray, clip_limit=2.0, tile_size=8)
        
        # 6. Denoise (removes crumpled spots, shadow stains)
        denoised = cls.reduce_noise(enhanced)
        
        # 7. De-skew
        de_skewed = cls.de_skew(denoised)
        
        # 8. Sharpen (blurry mobile captures)
        sharpened = ImageUtils.sharpen_image(de_skewed, strength=1.0)
        
        # 9. High-contrast adaptive binarization (yields clean black & white text sheet)
        final_processed = cls.adaptive_binarize(sharpened)
        
        # Save output for review/verification
        if save_path:
            cv2.imwrite(save_path, final_processed)
            logger.info(f"Preprocessed image output saved at: {save_path}")
            
        return final_processed

    @classmethod
    def preprocess_for_vision(cls, image_path: str, save_path: str = None) -> np.ndarray:
        """
        Lighter preprocessing pipeline optimized for Vision-Language Models.
        VLMs work better with natural-looking images (not binarized).
        
        Pipeline: Load -> Perspective Correct -> Resolution Normalize -> 
                  CLAHE Contrast -> Light Denoise -> Sharpen
        """
        logger.info(f"Preprocessing image for VLM analysis: {image_path}")
        
        # 1. Load image (keep in color for VLM)
        img = cls.read_image(image_path)
        
        # 2. Perspective correction
        img = ImageUtils.correct_perspective(img)
        
        # 3. Resolution normalization
        img = ImageUtils.normalize_resolution(img, target_dpi=300, current_dpi=72)
        
        # 4. Light denoising (preserve color information)
        denoised = cv2.bilateralFilter(img, 5, 50, 50)
        
        # 5. Light sharpening
        sharpened = ImageUtils.sharpen_image(denoised, strength=0.5)
        
        if save_path:
            cv2.imwrite(save_path, sharpened)
            logger.info(f"VLM-preprocessed image saved at: {save_path}")
        
        return sharpened
