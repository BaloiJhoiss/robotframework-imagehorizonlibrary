# -*- coding: utf-8 -*-
#from os import listdir
#from os.path import abspath, basename, dirname, isdir, isfile, splitext, join as path_join
from pathlib import Path
from typing import List, Union, Type
from enum import Enum
from time import time, sleep
from re import match  # added regex
from contextlib import contextmanager
from robot.libraries.BuiltIn import BuiltIn

import pyautogui as ag
from robot.api import logger as LOGGER

# ``cv2`` imports ``numpy`` internally.  Import ``numpy`` explicitly first to
# ensure it is loaded only once and avoid "module reloaded" warnings on Python
# 3.12+.


try:  # pragma: no cover - optional dependency
    import numpy as np
    import cv2
    # ``DictValue`` vanished from some OpenCV builds.  Tests exercising the
    # DNN module expect it to exist, so provide a tiny stand‑in when missing to
    # keep the library importable.  Accessing ``cv2.dnn`` may itself raise an
    # exception on some installations (or when mocked) so guard lookups
    # carefully.
    try:  # pragma: no cover - defensive lookup
        dnn_mod = getattr(cv2, "dnn", None)
    except Exception:
        dnn_mod = None
    if dnn_mod is not None and not hasattr(dnn_mod, "DictValue"):
        class _DummyDictValue:
            def __init__(self, *args, **kwargs):
                self.value = args[0] if args else None

            def __iter__(self):  # minimal interface used in tests
                return iter((self.value,))

        try:
            setattr(dnn_mod, "DictValue", _DummyDictValue)
        except Exception:  # pragma: no cover - attribute may be read-only
            pass
except Exception:  # pragma: no cover - graceful fallback when cv2 is missing
    np = None
    cv2 = None

import traceback


from ..errors import (
    ImageNotFoundException,
    InvalidImageException,
    #ReferenceFolderException,
    #ScreenshotFolderException,
    #StrategyException,
    ImageNotInPath,
    PathNotSetException
)


def _is_pyautogui_image_not_found(exc):
    image_not_found = getattr(ag, "ImageNotFoundException", None)
    return isinstance(image_not_found, type) and isinstance(exc, image_not_found)

# class ImagePathTypeEnum(Enum):
#     STR_TYPE = True
#     LIST_TYPE = False


class _RecognizeImages(object):
    """
    The _RecognizeImages class is a Robot Framework library designed to manage and retrieve image file paths.
    It creates a lookup table of image names (without the .png extension) and their absolute paths,
    allowing for quick and efficient access to image files from one or more specified directories.
    The library is specifically tailored to handle .png files.
    """
    DFLT_TIMEOUT = 0
    PIXEL_RATIO =0.0


    @contextmanager
    def _suppress_keyword_on_failure(self):
        """Temporarily disable post-failure keyword during a block."""
        keyword = self.keyword_on_failure
        self.keyword_on_failure = None
        yield None
        self.keyword_on_failure = keyword



      
    def get_reference_folder(self) -> Union[List[str], str]:
        """
        Description: Returns the currently set reference folder(s).

        Returns: A string or a list of strings representing the path(s) to the reference folder(s).

        Example:
            ${ref_path} =    Get Reference Folder
            Log    Current reference path: ${ref_path}
        :return:
        """
        return self.reference_folder
    


    def __count_track_mode_screenshots(self, track_mode_path: Path):
        count = 0
        for file in track_mode_path.iterdir():
            if match(r"track_mode-(\d+)\.png",file.name):
                count +=1
        return count

    def _locate_image(self, reference_image, timeout=0, grayscale=None, region=None, log_it=True):
        pic=None
        path = None
        best_score = None
        if self.track_mode:
            track_mode_path =Path(str(self.screenshot_folder)) if self.screenshot_folder  else Path.cwd()
            count = self.__count_track_mode_screenshots(track_mode_path)
            path = track_mode_path / f"track_mode-{count}.png"
            print(f"Path: {path}")
            pic = ag.screenshot()
            pic.save(path)
        ## TODO: This requires a rework, may not need if isinstance
        #correlating_image_path = self.look_up_table[reference_image.replace(".png", "")]
        loc, score, scale = self._try_locate(reference_image)
        if score is not None and (best_score is None or score > best_score):
            best_score = score
        if loc is None:
            return None

        if hasattr(loc, "left") and hasattr(loc, "top"):
            left, top, width, height = loc.left, loc.top, loc.width, loc.height
        else:
            left, top, width, height = tuple(loc)[:4]
        x = left + width / 2
        y = top + height / 2
        ## TODO: ignored for  now
        if self.PIXEL_RATIO == 0.0:
            self.get_pixel_ratio()
        if self.PIXEL_RATIO > 1:
            x = x / self.PIXEL_RATIO
            y = y / self.PIXEL_RATIO
        ### Until here ###
        if log_it:
            LOGGER.info(
                'Image "%s" found at %r (score %.3f, scale %.2f, strategy: %s)'
                % (
                    reference_image,
                    (x, y),
                    score if score is not None else float('nan'),
                    scale,
                    self.strategy,
                )
            )
        if pic:
            template_image_path = reference_image
            self.mark_image_location(path,template_image_path , path)
        return (x, y, score, scale)



    def get_pixel_ratio(self):
        """Calculate display pixel ratio once and cache it."""
        try:
            ratio = ag.screenshot().size[0] / ag.size().width
            self.PIXEL_RATIO = float(ratio)
        except Exception:
            self.PIXEL_RATIO = 1.0

    def mark_image_location(self, source_path, template_path, output_path):
        """
        Finds and marks the location of a template image within a source image.
        """
        # 1. Load the images
        img_bgr = cv2.imread(source_path)
        template = cv2.imread(template_path)

        if img_bgr is None or template is None:
            print("Error: Could not load one or both images.")
            return

        # Get the dimensions of the template
        w, h = template.shape[1], template.shape[0]

        # 2. Template Matching
        # Use a standard matching method (e.g., TM_CCOEFF_NORMED is robust)
        method = cv2.TM_CCOEFF_NORMED
        result = cv2.matchTemplate(img_bgr, template, method)

        # 3. Find Best Match
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_CCOEFF_NORMED, the best match is the maximum value
        top_left = max_loc
        
        # Calculate the bottom-right corner of the bounding box
        bottom_right = (top_left[0] + w, top_left[1] + h)

        # 4. Draw Bounding Box
        # Draw a green rectangle with a thickness of 2
        color = (0, 255, 0) # Green in BGR format
        thickness = 2
        cv2.rectangle(img_bgr, top_left, bottom_right, color, thickness)
        
        # Optional: Display the results
        # Convert from BGR to RGB for matplotlib display
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB) 
        
        #plt.imshow(img_rgb)
        #plt.title(f"Template Found (Confidence: {max_val:.4f})")
        #plt.axis('off')
        #plt.show()

        # Save the resulting image
        cv2.imwrite(output_path, img_bgr)
        print(f"Result saved to {output_path}")

    # def _run_on_failure(self):
    #     if not self.keyword_on_failure:
    #         return
    #     try:
    #         BuiltIn().run_keyword(self.keyword_on_failure)
    #     except Exception as e:
    #         LOGGER.debug(e)
    #         LOGGER.warning("Failed to take a screenshot. " "Is Robot Framework running?")

    

    
    def debug_image(self, reference_folder=None, minimize=False, dialog_default_dir=None):
        """Halts the test execution and opens the image debugger UI.

        Whenever you encounter problems with the recognition accuracy of a reference image,
        you should place this keyword just before the line in question. Example:

        | Debug Image
        | Wait For  hard_to_find_button

        The test will halt at this position and open the debugger UI. Use it as follows:

        - Select the reference image (`hard_to_find_button`)
        - Click the button "Detect reference image" for the strategy you want to test (default/edge). The GUI hides itself while it takes the screenshot of the current application when ``minimize`` is ``True``.
        - The Image Viewer at the botton shows the screenshot with all regions where the reference image was found.
        - "Matches Found": More than one match means that either `conficence` is set too low or that the reference image is visible multiple times. If the latter is the case, you should first detect a unique UI element and use relative keywords like `Click To The Right Of`.
        - "Max peak value" (only `edge`) gives feedback about the detection accuracy of the best match and is measured as a float number between 0 and 1. A peak value above _confidence_ results in a match.
        - "Edge detection debugger" (only `edge`) opens another window where both the reference and screenshot images are shown before and after the edge detection and is very helpful to loearn how the sigma and low/high threshold parameters lead to different results.
        - The field "Keyword to use this strategy" shows how to set the strategy to the current settings. Just copy the line and paste it into the test:

        | Set Strategy  edge  edge_sigma=2.0  edge_low_threshold=0.1  edge_high_threshold=0.3
        | Wait For  hard_to_find_button

        ``reference_folder`` can be given to temporarily override the folder
        from which reference images are loaded.

        ``minimize`` controls whether the debugger window is minimised before
        taking a screenshot. By default the window is kept visible; set
        ``minimize`` to ``True`` to minimise it. When visible, the window's area
        is masked so that matches inside the debugger are ignored.

        ``dialog_default_dir`` specifies the folder shown when the directory
        chooser is opened and the current reference folder is invalid or not
        accessible. If omitted, the user's home directory is used.

        The purpose of this keyword is *solely for debugging purposes*; don't
        use it in production!"""
        from .ImageDebugger import ImageDebugger

        previous_reference_folder = self.reference_folder
        if reference_folder is not None:
            self.set_reference_folder(reference_folder)
        try:
            debug_app = ImageDebugger(
                self,
                minimize=minimize,
                dialog_default_dir=dialog_default_dir,
            )
        finally:
            if reference_folder is not None:
                self.set_reference_folder(previous_reference_folder)


class _StrategyPyautogui:
    """Image matching strategy based on PyAutoGUI."""

    def __init__(self, image_horizon_instance):
        """Store reference to the owning ImageHorizonLibrary instance."""
        self.ih_instance = image_horizon_instance

    def _try_locate(self, ref_image, haystack_image=None, locate_all=False):
        """Locate a reference image using PyAutoGUI's matching.

        Parameters
        ----------
        ref_image : str
            Path to the reference image.
        haystack_image : image, optional
            Screenshot to search in. If ``None``, a screenshot is taken.
        locate_all : bool, optional
            If ``True``, return all matches; otherwise only the first match.

        Returns
        -------
        list or tuple
            When ``locate_all`` is ``False`` a tuple ``(location, score, scale)``
            is returned. ``location`` may be ``None`` if no match was found. When
            ``locate_all`` is ``True`` a list of such tuples is returned.
        """
        import numpy as np
        ih = self.ih_instance

        if haystack_image is None:
            haystack_image = ag.screenshot()

        if getattr(ih, "has_cv", False) and getattr(ih, "scale_enabled", False):
            haystack_np = np.array(haystack_image)
            if haystack_np.ndim == 3:
                haystack_gray = cv2.cvtColor(haystack_np, cv2.COLOR_RGB2GRAY)
            else:
                haystack_gray = haystack_np
            needle_gray = cv2.imread(ref_image, cv2.IMREAD_GRAYSCALE)
            scales = np.linspace(ih.scale_min, ih.scale_max, ih.scale_steps)
            confidence = ih.confidence or 0.9
            if locate_all:
                matches = []
                for scale in scales:
                    scaled_height = max(1, int(needle_gray.shape[0] * scale))
                    scaled_width = max(1, int(needle_gray.shape[1] * scale))
                    if (
                        scaled_height > haystack_gray.shape[0]
                        or scaled_width > haystack_gray.shape[1]
                    ):
                        continue
                    scaled_needle = cv2.resize(
                        needle_gray,
                        (scaled_width, scaled_height),
                        interpolation=cv2.INTER_AREA,
                    )
                    res = cv2.matchTemplate(
                        haystack_gray, scaled_needle, cv2.TM_CCOEFF_NORMED
                    )
                    peaks = np.where(res >= confidence)
                    for y, x in zip(*peaks):
                        matches.append(
                            (
                                (x, y, scaled_width, scaled_height),
                                float(res[y][x]),
                                scale,
                            )
                        )
                return matches
            else:
                best_loc = None
                best_score = -1.0
                best_scale = 1.0
                for scale in scales:
                    scaled_height = max(1, int(needle_gray.shape[0] * scale))
                    scaled_width = max(1, int(needle_gray.shape[1] * scale))
                    if (
                        scaled_height > haystack_gray.shape[0]
                        or scaled_width > haystack_gray.shape[1]
                    ):
                        continue
                    scaled_needle = cv2.resize(
                        needle_gray,
                        (scaled_width, scaled_height),
                        interpolation=cv2.INTER_AREA,
                    )
                    res = cv2.matchTemplate(
                        haystack_gray, scaled_needle, cv2.TM_CCOEFF_NORMED
                    )
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val > best_score:
                        best_score = float(max_val)
                        best_loc = (
                            max_loc[0],
                            max_loc[1],
                            scaled_width,
                            scaled_height,
                        )
                        best_scale = scale
                if best_loc is None or best_score < confidence:
                    return (None, best_score if best_score >= 0 else None, best_scale)
                return (best_loc, best_score, best_scale)

        if locate_all:
            locate_func = ag.locateAll
        else:
            locate_func = ag.locate  # Copy below,take screenshots

        with ih._suppress_keyword_on_failure():
            try:
                if ih.has_cv and ih.confidence:
                    location_res = locate_func(
                        ref_image, haystack_image, confidence=ih.confidence
                    )
                else:
                    if ih.confidence:
                        LOGGER.warn(
                            "Can't set confidence because you don't "
                            "have OpenCV (python3-opencv) installed "
                            "or a confidence level was not given."
                        )
                    location_res = locate_func(ref_image, haystack_image)
            except ImageNotFoundException:
                location_res = None
            except Exception as ex:
                if not _is_pyautogui_image_not_found(ex):
                    raise
                location_res = None

        if locate_all:
            if location_res is None:
                locations = []
            else:
                locations = [tuple(box) for box in location_res]
            scores = []
            if ih.has_cv and locations:
                try:
                    haystack_np = np.array(haystack_image)
                    if haystack_np.ndim == 3:
                        haystack_gray = cv2.cvtColor(haystack_np, cv2.COLOR_RGB2GRAY)
                    else:
                        haystack_gray = haystack_np
                    needle_gray = cv2.imread(ref_image, cv2.IMREAD_GRAYSCALE)
                    result = cv2.matchTemplate(
                        haystack_gray, needle_gray, cv2.TM_CCOEFF_NORMED
                    )
                    for x, y, w, h in locations:
                        scores.append(float(result[y][x]))
                except Exception:
                    scores = [None] * len(locations)
            else:
                scores = [None] * len(locations)
            return [(loc, scr, 1.0) for loc, scr in zip(locations, scores)]

        location = location_res
        score = None
        if ih.has_cv and location is not None:
            try:
                haystack_np = np.array(haystack_image)
                if haystack_np.ndim == 3:
                    haystack_gray = cv2.cvtColor(haystack_np, cv2.COLOR_RGB2GRAY)
                else:
                    haystack_gray = haystack_np
                needle_gray = cv2.imread(ref_image, cv2.IMREAD_GRAYSCALE)
                res = cv2.matchTemplate(
                    haystack_gray, needle_gray, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, _ = cv2.minMaxLoc(res)
                score = float(max_val)
            except Exception:
                score = None
        return (location, score, 1.0)
    
class _StrategyCv2:
    """Image matching strategy using OpenCV edge detection."""

    _CV_DEFAULT_CONFIDENCE = 0.9
    # assumes default of 0.9 if value is not passed. Why not 0.99?

    def __init__(self, image_horizon_instance):
        """Store reference to the owning ImageHorizonLibrary instance."""
        self.ih_instance = image_horizon_instance # ?

    def _try_locate(self, ref_image, haystack_image=None, locate_all=False):
        """Locate a reference image using OpenCV edge detection.

        Parameters
        ----------
        ref_image : str
            Path to the reference image.
        haystack_image : array-like, optional
            Screenshot to search in. If ``None``, a screenshot is taken.
        locate_all : bool, optional
            If ``True``, return all matches for debugging.

        Returns
        -------
        tuple or list
            When ``locate_all`` is ``False``: ``(location, score, scale)`` or
            ``(None, score, scale)`` if not found.
            When ``locate_all`` is ``True``: a list of such tuples for each
            detected match.
        """
        import numpy as np
        ih = self.ih_instance
        confidence = ih.confidence or self._CV_DEFAULT_CONFIDENCE
        # setting confidence
        with ih._suppress_keyword_on_failure():
            needle_img = cv2.imread(ref_image, cv2.IMREAD_GRAYSCALE)
            if haystack_image is None:
                haystack_img_gray = cv2.cvtColor(
                    np.array(ag.screenshot()), cv2.COLOR_RGB2GRAY
                )# if no haystack is passed, make a screenshot
            else:
                if len(haystack_image.shape) == 2:
                    # if haystack has a shape of two, it is assumed 2??
                    haystack_img_gray = haystack_image
                else:
                    haystack_img_gray = cv2.cvtColor(
                        haystack_image, cv2.COLOR_BGR2GRAY
                    )# is equal to .shape==2

            ih.haystack_edge = self.detect_edges(haystack_img_gray)

            if ih.scale_enabled:
                scales = np.linspace(ih.scale_min, ih.scale_max, ih.scale_steps)
            else:
                scales = [1.0]
            best_location = None
            best_scale = 1.0
            best_score = -1.0
            best_needle = None
            locations = []

            for scale in scales:
                scaled_height = max(1, int(needle_img.shape[0] * scale))
                scaled_width = max(1, int(needle_img.shape[1] * scale))
                scaled_needle = cv2.resize(
                    needle_img,
                    (scaled_width, scaled_height),
                    interpolation=cv2.INTER_AREA,
                )
                needle_edge = self.detect_edges(scaled_needle)
                haystack_edge_uint8 = (ih.haystack_edge * 255).astype(np.uint8)
                needle_edge_uint8 = (needle_edge * 255).astype(np.uint8)
                peakmap = cv2.matchTemplate(
                    haystack_edge_uint8, needle_edge_uint8, cv2.TM_CCOEFF_NORMED
                )

                if locate_all:
                    peaks = np.where(peakmap >= confidence)
                    for y, x in zip(*peaks):
                        peak = peakmap[y][x]
                        if peak > confidence:
                            loc = (x, y, scaled_width, scaled_height)
                            locations.append((loc, peak, scale))
                        if peak > best_score:
                            best_score = peak
                            best_scale = scale
                            best_location = loc
                            ih.needle_edge = needle_edge
                            ih.peakmap = peakmap
                            best_needle = scaled_needle
                else:
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(peakmap)
                    peak = max_val
                    x, y = max_loc
                    if peak > best_score:
                        best_score = peak
                        best_scale = scale
                        best_location = (
                            x,
                            y,
                            scaled_width,
                            scaled_height,
                        )
                        ih.needle_edge = needle_edge
                        ih.peakmap = peakmap
                        best_needle = scaled_needle

            if locate_all:
                return locations

            if best_score > confidence and ih.validate_match and ih.has_cv:
                margin = ih.validation_margin or 0
                haystack_uint8 = haystack_img_gray.astype(np.uint8)
                needle_uint8 = best_needle.astype(np.uint8)
                x0 = int(max(0, best_location[0] - margin))
                y0 = int(max(0, best_location[1] - margin))
                x1 = int(
                    min(
                        haystack_uint8.shape[1],
                        best_location[0] + best_location[2] + margin,
                    )
                )
                y1 = int(
                    min(
                        haystack_uint8.shape[0],
                        best_location[1] + best_location[3] + margin,
                    )
                )
                region = haystack_uint8[y0:y1, x0:x1]
                if region.shape[0] >= needle_uint8.shape[0] and region.shape[1] >= needle_uint8.shape[1]:
                    res = cv2.matchTemplate(
                        region, needle_uint8, cv2.TM_CCOEFF_NORMED
                    )
                    if res.size == 0 or res.max() < confidence:
                        return None, best_score, best_scale

            if best_score > confidence:
                return best_location, best_score, best_scale
            return None, best_score, best_scale

    def _auto_edge_parameters(self, img):
        """Derive edge detection parameters from image statistics.

        Parameters
        ----------
        img : array-like
            Grayscale image data.

        Returns
        -------
        tuple
            Tuple ``(sigma, low, high)`` containing suitable parameters for the
            Canny edge detector.

        Notes
        -----
        If the image uses 8-bit integers, it is converted to floating point so
        that thresholding works reliably. ``cv2.threshold`` with ``OTSU``
        provides a reasonable high threshold, while the standard deviation of
        the image is used to scale ``sigma`` and the low threshold is derived as
        a fraction of the high threshold.
        """

        # ``img`` may be provided as a list or other array-like type; make sure
        # we are working with a NumPy array of floats to avoid type promotion
        # issues which manifested as ``umr_maximum``/``float`` errors on some
        # platforms.
        import numpy as np
        img_float = np.asarray(img, dtype=np.float64)
        max_val = float(np.max(img_float)) if img_float.size else 0.0
        if max_val > 1.0:
            img_float /= 255.0

        std = float(np.std(img_float))
        sigma = float(np.clip(std * 3, 0.1, 5.0))

        img_uint8 = np.rint(img_float * 255).astype(np.uint8)
        t, _ = cv2.threshold(img_uint8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        t = float(t) / 255.0
        low = float(max(0.0, t * 0.5))
        high = float(min(1.0, t * 1.5))
        if high <= low:
            high = float(min(1.0, low + 0.05))

        return float(sigma), float(low), float(high)

    def _detect_edges(self, img, sigma, low, high):
        """Run Canny edge detection with optional preprocessing.

        Available filters for preprocessing are ``gaussian``, ``median``,
        ``erode`` and ``dilate``. Preprocessing is only performed when the
        ``edge_preprocess`` option is set *and* OpenCV is available.

        Parameters
        ----------
        img : array-like
            Grayscale image data.
        sigma : float
            Standard deviation of the Gaussian blur applied before edge
            detection.
        low : float
            Lower gradient magnitude threshold (0.0–1.0).
        high : float
            Upper gradient magnitude threshold (0.0–1.0).

        Returns
        -------
        array-like
            Edge-detected binary image.
        """
        import numpy as np
        preprocess = self.ih_instance.edge_preprocess
        ksize = int(self.ih_instance.edge_kernel_size or 3)

        img_float = img.astype(np.float32)
        if img_float.max() > 1.0:
            img_uint8 = img_float.astype(np.uint8)
        else:
            img_uint8 = (img_float * 255).astype(np.uint8)

        if preprocess and self.ih_instance.has_cv:
            if preprocess == "gaussian":
                img_uint8 = cv2.GaussianBlur(img_uint8, (ksize, ksize), 0)
            elif preprocess == "median":
                img_uint8 = cv2.medianBlur(img_uint8, ksize)
            elif preprocess == "erode":
                img_uint8 = cv2.erode(img_uint8, np.ones((ksize, ksize), np.uint8))
            elif preprocess == "dilate":
                img_uint8 = cv2.dilate(img_uint8, np.ones((ksize, ksize), np.uint8))

        if sigma and sigma > 0:
            img_uint8 = cv2.GaussianBlur(img_uint8, (0, 0), sigma)

        edge_img = cv2.Canny(img_uint8, int(low * 255), int(high * 255))
        return edge_img.astype(np.float32) / 255.0

    def detect_edges(self, img):
        """Apply edge detection on a given image.

        Parameters
        ----------
        img : array-like
            Grayscale image data to process.

        Returns
        -------
        array-like
            Binary edge image computed with the Canny detector. If explicit
            parameters are not provided, sensible defaults are derived from the
            image statistics.
        """

        sigma = self.ih_instance.edge_sigma
        low = self.ih_instance.edge_low_threshold
        high = self.ih_instance.edge_high_threshold
        try:
            sigma = float(sigma) if sigma is not None else None
            low = float(low) if low is not None else None
            high = float(high) if high is not None else None
        except (TypeError, ValueError):
            sigma = low = high = None

        if sigma is None or low is None or high is None:
            auto_sigma, auto_low, auto_high = self._auto_edge_parameters(img)
            if sigma is None:
                sigma = auto_sigma
            if low is None:
                low = auto_low
            if high is None:
                high = auto_high

        return self._detect_edges(img, sigma, low, high)
