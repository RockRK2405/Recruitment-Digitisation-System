"""
Advanced Image Utilities for Multi-Modal Document Intelligence.

Provides production-grade image manipulation, enhancement, and extraction
utilities for handling scanned resumes, mobile camera photos, certificates,
ID cards, and multi-page documents in industrial recruitment workflows.
"""

import os
import io
import math
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional
from config.logging_config import logger

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Advanced image processing will be limited.")


class ImageUtils:
    """Production-grade image processing utilities for document intelligence."""

    # ─────────────────────────────────────────────
    # TEXT ORIENTATION DETECTION
    # ─────────────────────────────────────────────
    @staticmethod
    def detect_text_orientation(image: np.ndarray) -> float:
        """
        Detects text orientation angle in a document image.
        Uses Hough Line Transform to find dominant text line angles.
        
        Args:
            image: Input image as numpy array (grayscale or BGR)
            
        Returns:
            Detected angle in degrees (0 = horizontal, positive = clockwise)
        """
        if not _CV2_AVAILABLE:
            return 0.0

        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)

            # Hough Line Transform to detect straight lines
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, threshold=100,
                minLineLength=min(gray.shape) // 4,
                maxLineGap=10
            )

            if lines is None or len(lines) == 0:
                return 0.0

            # Calculate angles of all detected lines
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 == 0:
                    continue
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                # Only consider near-horizontal lines (typical text lines)
                if abs(angle) < 45:
                    angles.append(angle)

            if not angles:
                return 0.0

            # Return median angle (robust against outliers)
            median_angle = float(np.median(angles))
            logger.info(f"Detected text orientation: {median_angle:.2f} degrees")
            return median_angle

        except Exception as e:
            logger.warning(f"Text orientation detection failed: {str(e)}")
            return 0.0

    # ─────────────────────────────────────────────
    # PERSPECTIVE CORRECTION
    # ─────────────────────────────────────────────
    @staticmethod
    def correct_perspective(image: np.ndarray) -> np.ndarray:
        """
        Detects document corners and applies perspective warp to produce
        a flat, rectangular view. Essential for mobile camera captures
        taken at angles.
        
        Args:
            image: Input BGR image
            
        Returns:
            Perspective-corrected image
        """
        if not _CV2_AVAILABLE:
            return image

        try:
            orig = image.copy()
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Edge detection
            edged = cv2.Canny(blurred, 75, 200)

            # Dilate to close gaps in edge contours
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            edged = cv2.dilate(edged, kernel, iterations=1)

            # Find contours
            contours, _ = cv2.findContours(
                edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
            )

            # Sort contours by area (largest first)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

            doc_contour = None
            for contour in contours:
                # Approximate contour to polygon
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

                # Check if it's a quadrilateral and large enough
                if len(approx) == 4:
                    area = cv2.contourArea(approx)
                    img_area = gray.shape[0] * gray.shape[1]
                    # Document should be at least 20% of image area
                    if area > img_area * 0.2:
                        doc_contour = approx
                        break

            if doc_contour is None:
                logger.info("No document quadrilateral detected. Skipping perspective correction.")
                return orig

            # Order points: top-left, top-right, bottom-right, bottom-left
            pts = doc_contour.reshape(4, 2).astype(np.float32)
            rect = _order_points(pts)

            # Compute output dimensions
            (tl, tr, br, bl) = rect
            width_a = np.linalg.norm(br - bl)
            width_b = np.linalg.norm(tr - tl)
            max_width = int(max(width_a, width_b))

            height_a = np.linalg.norm(tr - br)
            height_b = np.linalg.norm(tl - bl)
            max_height = int(max(height_a, height_b))

            # Destination points
            dst = np.array([
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1]
            ], dtype=np.float32)

            # Apply perspective warp
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(orig, M, (max_width, max_height))

            logger.info(f"Perspective correction applied. Output size: {max_width}x{max_height}")
            return warped

        except Exception as e:
            logger.warning(f"Perspective correction failed: {str(e)}. Returning original image.")
            return image

    # ─────────────────────────────────────────────
    # RESOLUTION NORMALIZATION
    # ─────────────────────────────────────────────
    @staticmethod
    def normalize_resolution(image: np.ndarray, target_dpi: int = 300, current_dpi: int = 72) -> np.ndarray:
        """
        Scales image to a standard DPI for consistent OCR accuracy.
        Mobile camera photos typically default to 72 DPI while scanners produce 200-600 DPI.
        
        Args:
            image: Input image
            target_dpi: Desired output DPI (default 300 for optimal OCR)
            current_dpi: Estimated current DPI of the source image
            
        Returns:
            Resolution-normalized image
        """
        if not _CV2_AVAILABLE:
            return image

        try:
            scale_factor = target_dpi / current_dpi

            # Don't upscale beyond 2x (diminishing returns, adds noise)
            scale_factor = min(scale_factor, 2.0)

            # Don't downscale too aggressively
            scale_factor = max(scale_factor, 0.5)

            if abs(scale_factor - 1.0) < 0.05:
                return image  # Already at target resolution

            h, w = image.shape[:2]
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)

            # Use INTER_CUBIC for upscaling, INTER_AREA for downscaling
            interpolation = cv2.INTER_CUBIC if scale_factor > 1.0 else cv2.INTER_AREA
            resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)

            logger.info(
                f"Resolution normalized: {w}x{h} -> {new_w}x{new_h} "
                f"(scale: {scale_factor:.2f}x, target: {target_dpi} DPI)"
            )
            return resized

        except Exception as e:
            logger.warning(f"Resolution normalization failed: {str(e)}")
            return image

    # ─────────────────────────────────────────────
    # CONTRAST ENHANCEMENT (CLAHE)
    # ─────────────────────────────────────────────
    @staticmethod
    def enhance_contrast_clahe(image: np.ndarray, clip_limit: float = 2.0, tile_size: int = 8) -> np.ndarray:
        """
        Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) 
        for local contrast enhancement. Dramatically improves readability
        of faded text, low-contrast scans, and poorly-lit mobile captures.
        
        Args:
            image: Input grayscale image
            clip_limit: Contrast clipping limit (higher = more contrast)
            tile_size: Grid size for local histogram equalization
            
        Returns:
            Contrast-enhanced image
        """
        if not _CV2_AVAILABLE:
            return image

        try:
            # Ensure grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Create CLAHE object
            clahe = cv2.createCLAHE(
                clipLimit=clip_limit,
                tileGridSize=(tile_size, tile_size)
            )

            enhanced = clahe.apply(gray)
            logger.info(f"CLAHE contrast enhancement applied (clip={clip_limit}, tiles={tile_size}x{tile_size})")
            return enhanced

        except Exception as e:
            logger.warning(f"CLAHE enhancement failed: {str(e)}")
            return image

    # ─────────────────────────────────────────────
    # IMAGE SHARPENING
    # ─────────────────────────────────────────────
    @staticmethod
    def sharpen_image(image: np.ndarray, strength: float = 1.5) -> np.ndarray:
        """
        Applies unsharp masking to sharpen blurry images from mobile cameras.
        Enhances text edges without amplifying noise excessively.
        
        Args:
            image: Input image (grayscale or BGR)
            strength: Sharpening strength (1.0 = mild, 2.0 = strong)
            
        Returns:
            Sharpened image
        """
        if not _CV2_AVAILABLE:
            return image

        try:
            # Create Gaussian blur as the "unsharp" mask
            blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=3)

            # Apply unsharp mask: sharpened = original + strength * (original - blurred)
            sharpened = cv2.addWeighted(image, 1.0 + strength, blurred, -strength, 0)

            logger.info(f"Image sharpened with unsharp mask (strength={strength})")
            return sharpened

        except Exception as e:
            logger.warning(f"Image sharpening failed: {str(e)}")
            return image

    # ─────────────────────────────────────────────
    # PDF EMBEDDED IMAGE EXTRACTION
    # ─────────────────────────────────────────────
    @staticmethod
    def extract_images_from_pdf(pdf_path: str, output_dir: Optional[str] = None) -> List[str]:
        """
        Extracts embedded images from PDF files.
        Handles photos, scanned pages, and inline graphics.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images (defaults to same dir as PDF)
            
        Returns:
            List of file paths to extracted images
        """
        extracted_paths = []
        
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path)
        os.makedirs(output_dir, exist_ok=True)

        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            img_count = 0

            for page_num, page in enumerate(reader.pages):
                if "/XObject" not in (page.get("/Resources") or {}):
                    continue

                x_objects = page["/Resources"]["/XObject"].get_object()

                for obj_name in x_objects:
                    x_obj = x_objects[obj_name].get_object()

                    if x_obj.get("/Subtype") == "/Image":
                        try:
                            # Determine image format
                            width = x_obj.get("/Width", 0)
                            height = x_obj.get("/Height", 0)

                            if width < 50 or height < 50:
                                continue  # Skip tiny icons/logos

                            data = x_obj.get_data()
                            img_count += 1

                            # Determine file extension from filter
                            filters = x_obj.get("/Filter", "")
                            if isinstance(filters, list):
                                filters = filters[0] if filters else ""
                            filters = str(filters)

                            if "/DCTDecode" in filters:
                                ext = ".jpg"
                            elif "/JPXDecode" in filters:
                                ext = ".jp2"
                            elif "/FlateDecode" in filters:
                                ext = ".png"
                            else:
                                ext = ".png"

                            # Save image
                            img_path = os.path.join(
                                output_dir,
                                f"{base_name}_page{page_num + 1}_img{img_count}{ext}"
                            )

                            if ext in [".jpg", ".jp2"]:
                                with open(img_path, "wb") as f:
                                    f.write(data)
                            else:
                                # Reconstruct from raw pixel data
                                try:
                                    color_space = str(x_obj.get("/ColorSpace", "/DeviceRGB"))
                                    if "/DeviceRGB" in color_space:
                                        mode = "RGB"
                                    elif "/DeviceGray" in color_space:
                                        mode = "L"
                                    else:
                                        mode = "RGB"

                                    img = Image.frombytes(mode, (width, height), data)
                                    img.save(img_path, format="PNG")
                                except Exception:
                                    with open(img_path, "wb") as f:
                                        f.write(data)

                            extracted_paths.append(img_path)
                            logger.info(
                                f"Extracted embedded image from PDF page {page_num + 1}: "
                                f"{width}x{height}px -> {img_path}"
                            )

                        except Exception as e:
                            logger.warning(f"Failed to extract image from page {page_num + 1}: {str(e)}")
                            continue

            logger.info(f"Total embedded images extracted from PDF: {len(extracted_paths)}")

        except ImportError:
            logger.warning("pypdf not available. Cannot extract embedded images from PDF.")
        except Exception as e:
            logger.error(f"PDF image extraction failed: {str(e)}")

        return extracted_paths

    # ─────────────────────────────────────────────
    # MULTI-PAGE TIFF HANDLING
    # ─────────────────────────────────────────────
    @staticmethod
    def split_multi_page_tiff(tiff_path: str, output_dir: Optional[str] = None) -> List[str]:
        """
        Splits multi-page TIFF documents into individual page images.
        Common format for industrial document scanners.
        
        Args:
            tiff_path: Path to multi-page TIFF file
            output_dir: Directory to save individual pages
            
        Returns:
            List of file paths to individual page images
        """
        page_paths = []

        if output_dir is None:
            output_dir = os.path.dirname(tiff_path)
        os.makedirs(output_dir, exist_ok=True)

        try:
            img = Image.open(tiff_path)
            base_name = os.path.splitext(os.path.basename(tiff_path))[0]
            page_num = 0

            while True:
                try:
                    img.seek(page_num)
                    page_path = os.path.join(output_dir, f"{base_name}_page{page_num + 1}.png")
                    # Convert to RGB if necessary
                    if img.mode not in ("RGB", "L"):
                        page_img = img.convert("RGB")
                    else:
                        page_img = img.copy()
                    page_img.save(page_path, format="PNG")
                    page_paths.append(page_path)
                    logger.info(f"Extracted TIFF page {page_num + 1} -> {page_path}")
                    page_num += 1
                except EOFError:
                    break

            logger.info(f"Split multi-page TIFF into {len(page_paths)} pages.")

        except Exception as e:
            logger.error(f"TIFF splitting failed: {str(e)}")

        return page_paths

    # ─────────────────────────────────────────────
    # IMAGE FORMAT VALIDATION & CONVERSION
    # ─────────────────────────────────────────────
    @staticmethod
    def validate_and_convert(file_path: str) -> Tuple[str, str]:
        """
        Validates an image file and converts HEIC/WebP/BMP to PNG if needed.
        
        Args:
            file_path: Path to the input image file
            
        Returns:
            Tuple of (converted_file_path, original_format)
        """
        ext = os.path.splitext(file_path)[1].lower()
        supported_direct = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

        if ext in supported_direct:
            return file_path, ext

        # Convert unsupported formats to PNG
        try:
            img = Image.open(file_path)
            converted_path = file_path + ".converted.png"
            img.convert("RGB").save(converted_path, format="PNG")
            logger.info(f"Converted {ext} image to PNG: {converted_path}")
            return converted_path, ext
        except Exception as e:
            logger.error(f"Image conversion failed for {ext}: {str(e)}")
            return file_path, ext

    # ─────────────────────────────────────────────
    # DOCUMENT REGION DETECTION
    # ─────────────────────────────────────────────
    @staticmethod
    def detect_document_regions(image: np.ndarray) -> List[dict]:
        """
        Detects distinct text regions/blocks in a document image.
        Useful for identifying separate sections in certificates,
        multi-column layouts, or composite documents.
        
        Args:
            image: Input image (grayscale or BGR)
            
        Returns:
            List of region dicts with keys: x, y, w, h, area
        """
        if not _CV2_AVAILABLE:
            return []

        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Threshold
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Dilate to merge nearby text into blocks
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 10))
            dilated = cv2.dilate(thresh, kernel, iterations=2)

            # Find contours of text blocks
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            regions = []
            img_area = gray.shape[0] * gray.shape[1]

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                # Filter out very small or very large regions
                if area > img_area * 0.005 and area < img_area * 0.95:
                    regions.append({
                        "x": int(x), "y": int(y),
                        "w": int(w), "h": int(h),
                        "area": int(area)
                    })

            # Sort top-to-bottom, then left-to-right
            regions.sort(key=lambda r: (r["y"], r["x"]))
            logger.info(f"Detected {len(regions)} text regions in document image.")
            return regions

        except Exception as e:
            logger.warning(f"Document region detection failed: {str(e)}")
            return []


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def _order_points(pts: np.ndarray) -> np.ndarray:
    """
    Orders four points in the sequence: top-left, top-right, bottom-right, bottom-left.
    Used for perspective transform calculations.
    """
    rect = np.zeros((4, 2), dtype=np.float32)

    # Sum of coordinates: top-left has smallest sum, bottom-right has largest
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right

    # Difference of coordinates: top-right has smallest diff, bottom-left has largest
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left

    return rect
