import os
import re
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import (
    get_tesseract_path,
    get_tessdata_prefix,
    DEFAULT_CODE_PATTERN,
    DEFAULT_CONFIDENCE_THRESHOLD,
)

class OCREngine:
    def __init__(self, code_pattern: str = DEFAULT_CODE_PATTERN,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        self.code_pattern_str = code_pattern
        self.code_regex = re.compile(code_pattern, re.IGNORECASE)
        self.confidence_threshold = confidence_threshold
        
        # Configure Tesseract path & environment
        tess_bin = get_tesseract_path()
        tess_data = get_tessdata_prefix()
        pytesseract.pytesseract.tesseract_cmd = tess_bin
        if tess_data:
            os.environ["TESSDATA_PREFIX"] = tess_data

    def set_pattern(self, new_pattern: str):
        self.code_pattern_str = new_pattern
        self.code_regex = re.compile(new_pattern, re.IGNORECASE)

    def extract_code(self, image_input: Any) -> Tuple[Optional[str], float, str, str]:
        """
        Process an image (filepath or numpy ndarray) and extract the alphanumeric code.
        Returns:
            (extracted_code, confidence, status, details)
            status can be: 'SUCCESS', 'NEEDS_REVIEW', or 'FAILED'
        """
        cv_img = self._load_image(image_input)
        if cv_img is None:
            return None, 0.0, "FAILED", "Unable to load image file"

        variants = self._generate_image_variants(cv_img)
        
        psm_modes = [6, 7, 11, 3]
        whitelist_cfg = r"-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."

        best_candidate: Optional[str] = None
        best_confidence: float = 0.0
        best_details: str = ""

        # Multi-pass OCR across preprocessed variants
        for v_name, v_img in variants:
            for psm in psm_modes:
                config = f"{whitelist_cfg} --psm {psm}"
                try:
                    data = pytesseract.image_to_data(v_img, config=config, output_type=pytesseract.Output.DICT)
                    words = [t.strip() for t in data["text"] if t.strip()]
                    if not words:
                        continue
                    
                    full_str = " ".join(words)
                    
                    # 1. Direct Regex Match on full string
                    matches = self.code_regex.findall(full_str)
                    if matches:
                        cand = matches[0].upper()
                        conf = self._compute_confidence(data, cand)
                        if conf >= self.confidence_threshold:
                            return cand, conf, "SUCCESS", f"Matched regex ({v_name}, psm {psm})"
                        elif conf > best_confidence:
                            best_candidate = cand
                            best_confidence = conf
                            best_details = f"Low confidence {conf:.1f}% ({v_name}, psm {psm})"

                    # 2. Check for punctuation variations (e.g. XXXX_XXXX_XXXX or XXXX.XXXX.XXXX or spaces)
                    norm_hyphen_str = re.sub(r'[\s_.:/]+', '-', full_str).upper()
                    norm_matches = self.code_regex.findall(norm_hyphen_str)
                    if norm_matches:
                        cand = norm_matches[0].upper()
                        conf = self._compute_confidence(data, cand) * 0.95
                        if conf >= self.confidence_threshold:
                            return cand, round(conf, 1), "SUCCESS", f"Normalized separators ({v_name}, psm {psm})"
                        elif conf > best_confidence:
                            best_candidate = cand
                            best_confidence = conf
                            best_details = f"Normalized low conf {conf:.1f}% ({v_name}, psm {psm})"

                    # 3. Check if hyphens were completely omitted in 12 consecutive chars
                    clean_alphanumeric = re.sub(r'[^A-Za-z0-9]', '', full_str).upper()
                    if len(clean_alphanumeric) == 12:
                        formatted = f"{clean_alphanumeric[:4]}-{clean_alphanumeric[4:8]}-{clean_alphanumeric[8:12]}"
                        if self.code_regex.match(formatted):
                            conf = self._compute_confidence(data, full_str) * 0.85
                            if conf > best_confidence:
                                best_candidate = formatted
                                best_confidence = conf
                                best_details = f"Recovered missing hyphens ({v_name}, psm {psm})"

                except Exception as ex:
                    continue

        if best_candidate:
            status = "SUCCESS" if best_confidence >= self.confidence_threshold else "NEEDS_REVIEW"
            return best_candidate, round(best_confidence, 1), status, best_details

        # If no code was found, try a raw string capture for user inspection
        try:
            raw_text = pytesseract.image_to_string(variants[0][1]).strip()
            raw_summary = raw_text[:30].replace("\n", " ") if raw_text else "No text detected"
            return None, 0.0, "NEEDS_REVIEW", f"Pattern not matched: '{raw_summary}'"
        except Exception:
            return None, 0.0, "FAILED", "OCR failed to detect valid code"

    def _load_image(self, image_input: Any) -> Optional[np.ndarray]:
        if isinstance(image_input, (str, Path)):
            path_str = str(image_input)
            if not os.path.exists(path_str):
                return None
            # Use imdecode to handle paths with unicode/special characters cleanly
            with open(path_str, "rb") as f:
                bytes_data = bytearray(f.read())
            arr = np.asarray(bytes_data, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, np.ndarray):
            return image_input
        elif isinstance(image_input, Image.Image):
            return cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
        return None

    def _generate_image_variants(self, cv_img: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """Generate optimized image variants for high-accuracy OCR."""
        variants = []
        h, w = cv_img.shape[:2]
        
        # Scaling factor: upscaling small text improves OCR dramatically
        scale_factor = 2.5 if max(h, w) < 1200 else 1.5
        new_w, new_h = int(w * scale_factor), int(h * scale_factor)
        scaled = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        variants.append(("scaled_gray", gray))

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(gray)
        variants.append(("clahe", contrast_enhanced))

        # Otsu Binarization
        _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(("otsu", thresh_otsu))

        # Inverted Otsu (white text on dark background)
        thresh_inv = cv2.bitwise_not(thresh_otsu)
        variants.append(("otsu_inv", thresh_inv))

        # Adaptive Gaussian Thresholding
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 31, 4)
        variants.append(("adaptive", adaptive))

        return variants

    def _compute_confidence(self, tesseract_data: Dict[str, Any], candidate_text: str) -> float:
        """Calculate average confidence of matching tokens from tesseract data."""
        conf_list = []
        for i, text in enumerate(tesseract_data["text"]):
            t_clean = text.strip().upper()
            if t_clean and any(part in candidate_text for part in t_clean.split("-")):
                try:
                    c = float(tesseract_data["conf"][i])
                    if c >= 0:
                        conf_list.append(c)
                except (ValueError, TypeError):
                    pass
        if conf_list:
            return sum(conf_list) / len(conf_list)
        return 80.0

