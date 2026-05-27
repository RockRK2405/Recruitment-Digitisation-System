import cv2
import numpy as np
from config.logging_config import logger

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
                    image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_RECLAIM
                )
                logger.info(f"De-skewed image by rotating {angle:.2f} degrees.")
                return rotated
        except Exception as e:
            logger.warning(f"De-skewing process skipped or failed: {str(e)}")
            
        return image

    @classmethod
    def preprocess(cls, image_path: str, save_path: str = None) -> np.ndarray:
        """
        Executes complete cleanup pipeline: Load -> Grayscale -> Denoise -> De-skew -> Binarize.
        Saves preprocessed image to save_path if specified.
        """
        logger.info(f"Preprocessing image file: {image_path}")
        
        # 1. Load image
        img = cls.read_image(image_path)
        
        # 2. Convert to gray
        gray = cls.to_grayscale(img)
        
        # 3. Denoise (removes crumpled spots, shadow stains)
        denoised = cls.reduce_noise(gray)
        
        # 4. De-skew
        de_skewed = cls.de_skew(denoised)
        
        # 5. High-contrast adaptive binarization (yields clean black & white text sheet)
        final_processed = cls.adaptive_binarize(de_skewed)
        
        # Save output for review/verification
        if save_path:
            cv2.imwrite(save_path, final_processed)
            logger.info(f"Preprocessed image output saved at: {save_path}")
            
        return final_processed
