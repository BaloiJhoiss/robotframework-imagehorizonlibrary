# -*- coding: utf-8 -*-
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from time import time,  sleep
from typing import Type, List, Union, Tuple
import inspect
import math

from ImageHorizonLibrary.errors import ImageNotFoundException


from .errors import *  # import errors before checking dependencies!

try:
    import pyautogui as ag
except KeyError as err:
    if err.args and err.args[0] == "DISPLAY":
        raise ImageHorizonLibraryError(
            "The DISPLAY environment variable is missing. "
            "Use Xvfb or set the DISPLAY variable to run GUI-based tests."
        ) from err
    raise
except ImportError as err:
    raise ImageHorizonLibraryError(
        "There is something wrong with pyautogui or it is not installed."
    ) from err

try:
    from robot.api import logger as LOGGER
    from robot.libraries.BuiltIn import BuiltIn
except ImportError:
    raise ImageHorizonLibraryError(
        "There is something wrong with " "Robot Framework or it is not installed."
    )

try:
    from tkinter import Tk as TK
except ImportError:
    raise ImageHorizonLibraryError(
        "There is either something wrong with "
        "Tkinter or you are running this on Java, "
        "which is not a supported platform. Please "
        "use Python and verify that Tkinter works."
    )

from . import utils
from .interaction import *
from .recognition import *
from .version import VERSION

__version__ = VERSION


def _is_pyautogui_image_not_found(exc):
    image_not_found = getattr(ag, "ImageNotFoundException", None)
    return isinstance(image_not_found, type) and isinstance(exc, image_not_found)


class ImageHorizonLibrary(
    _Keyboard, _Mouse, _OperatingSystem,_RecognizeImages, _Screenshot
):
    """A cross-platform Robot Framework library for GUI automation.

    *Key features*:
    - Automates *keyboard and mouse actions* on the screen (based on [https://pyautogui.readthedocs.org|pyautogui]).
    - The regions to execute these actions on (buttons, sliders, input fields etc.) are determined by `reference images` which the library detects on the screen - independently of the OS or the application type.
    - Two different image `recognition strategies`: `default` (fast and reliable of predictable screen content), and `edge` (to facilitate the recognition of unpredictable pixel deviations)
    - The library can also take screenshots in case of failure or by intention.
    - Search keywords return coordinates together with match score and optional detected scale.

    = Image Recognition =

    == Reference images ==
    ``reference_image`` parameter can be either a single file or a folder.
    If ``reference_image`` is a folder, image recognition is tried separately
    for each image in that folder, in alphabetical order until a match is found.

    For ease of use, reference image names are automatically normalized
    according to the following rules:

    - The name is lower cased: ``MYPICTURE`` and ``mYPiCtUrE`` become
      ``mypicture``

    - All spaces are converted to underscore ``_``: ``my picture`` becomes
      ``my_picture``

    - If the image name does not end in ``.png`` (case-insensitive), it will
      be added: ``mypicture`` becomes ``mypicture.png``.
    - The extension ``.PNG`` is also accepted. The name is normalized to
      lower case and a warning is logged if the provided case does not match
      the actual file on disk.

    - Path to _reference folder_ is prepended. This option must be given when
      `importing` the library.

    Using good names for reference images is evident from easy-to-read test
    data:

    | `Import Library` | ImageHorizonLibrary                   | reference_folder=images |                                                            |
    | `Click Image`    | popup Window title                    |                         | # Path is images/popup_window_title.png                    |
    | `Click Image`    | button Login Without User Credentials |                         | # Path is images/button_login_without_user_credentials.png |

    == Recognition strategies ==
    Basically, image recognition works by searching a reference image on the
    another image (a screnshot of the current desktop).
    If there is a region with 100% matching pixels of the reference image, this
    area represents a match.

    By default, the reference image must be an exakt sub-image of the screenshot.
    This works flawlessly in most cases.

    But problems can arise when:

    - the application's GUI uses transpareny effects
    - the screen resolution/the window size changes
    - font aliasing is used for dynamic text
    - compression algorithms in RDP/Citrix cause invisible artifacts
    - ...and in many more situations.

    In those situations, a certain amount of the pixels do not match.

    To solve this, ImageHorizon comes with a parameter ``confidence level``. This is a decimal value
    between 0 and 1 (inclusive) and defines how many percent of the reference image pixels
    must match the found region's imag. It is set to 1.0 = 100% by default.

    Confidence level can be set during `library importing` and re-adjusted during the test
    case with the keyword `Set Confidence`.

    === Default image detection strategy ===

    If imported without any strategy argument, the library uses [https://pyautogui.readthedocs.org|pyautogui]
    under the hood to recognize images on the screen.
    This is the perfect choice to start writing tests.

    To use `confidence level in mode` ``default`` the
    [https://pypi.org/project/opencv-python|opencv-python] Python package
    must be installed separately:

    | $ python3 -m pip install opencv-python

    After installation, the library will automatically use OpenCV for confidence
    levels lower than 1.0.

    === The "edge" image detection strategy ===

    The default image recognition reaches its limitations when the area to
    match contains a *disproportionate amount of unpredictable pixels*.

    The idea for this strategy came from a problem in real life: a web application
    showing a topographical map (loaded from a 3rd party provider), with a layer of
    interstate highways as black lines. For some reasons, the pixels of topographic
    areas between the highway lines (which are the vast majority) showed a slight
    deviation in brightness - invisible for the naked eye, but enough to make the test failing.

    The abstract and simplified example for this is a horizontal black line of 1px width in a
    matrix of 10x10 white pixels. To neglect a (slight) brightness deviation of the white pixels,
    you would need a confidence level of 0.1 which allows 90% of the pixels to be
    different. This is insanse and leads to inpredictable results.

    That's why ``edge`` was implemented as an alternative recognition strategy.
    The key here lies in the approach to *reduce both images* (reference and screenshot
    image) *to the essential characteristics* and then *compare _those_ images*.

    "Essential characteristics" of an image are those areas where neighbouring pixels show a
    sharp change of brightness, better known as "edges". [https://en.wikipedia.org/wiki/Edge_detection|Edge detection]
    is the process of finding the edges in an image, done by [https://opencv.org/|OpenCV] in this library.

    As a brief digression, edge detection is a multi-step process:

    - apply a [https://en.wikipedia.org/wiki/Gaussian_filter|Gaussian filter] (blurs the image to remove noise; intensity set by parameter `sigma`)
    - apply a [https://en.wikipedia.org/wiki/Sobel_operator|Sobel filter] (remove non-max pixels, get a 1 pixel edge curve)
    - separate weak edges from strong ones with [https://en.wikipedia.org/wiki/Canny_edge_detector#Edge_tracking_by_hysteresis|hysteresis]
    - apply the `template_matching` routine to get a [https://en.wikipedia.org/wiki/Cross-correlation|cross correlation] matrix of values from -1 (no correlation) to +1 (perfect correlation).
    - Filter out only those coordinates with values greater than the ``confidence`` level, take the max

    The keyword `Debug Image` opens a debugger UI where confidence level, Gaussian sigma and low/high thresholds can be tested and adjusted to individual needs. It also accepts optional ``reference_folder`` and ``minimize`` arguments to inspect images stored in a different location or hide the debugger window during screenshots (visible by default).

    Edge detection costs some extra CPU time; you should always first try
    to use the ``default`` strategy and only selectively switch to ``edge``
    when a confidence level below 0.9 is not sufficient to detect images reliably anymore:

    | # use with defaults (parameters auto-detected per image)
    | Set Strategy  edge
    | # use with custom parameters
    | Set Strategy  edge  edge_sigma=2.0  edge_low_threshold=0.1  edge_high_threshold=0.3  confidence=0.9
    | # enable edge preprocessing with a custom kernel
    | Set Strategy  edge  edge_preprocess=gaussian  edge_kernel_size=5

    Keywords like ``Wait For`` return ``(x, y, score, scale)`` where
    ``score`` is the match quality between -1 and 1 and
    ``scale`` is the detected resize factor (1.0 means no scaling).

    By default only a scale of ``1.0`` is considered during image search.
    To search over a range of scales (e.g. to support multiple screen
    resolutions), enable multi-scale search with ``Set Scale Range`` and
    disable it with ``Reset Scale Range``.


    = Performance =

    Locating images on screen, especially if screen resolution is large and
    reference image is also large, might take considerable time, regardless
    of the strategy.
    It is therefore advisable to save the returned coordinates if you are
    manipulating the same context many times in the row:

    | `Wait For`                   | label Name |     |
    | `Click To The Left Of Image` | label Name | 200 |

    In the above example, same image is located twice. Below is an example how
    we can leverage the returned location:

    | ${location}=           | `Wait For`  | label Name |
    | `Click To The Left Of` | ${location} | 200        |
    """

    ROBOT_LIBRARY_SCOPE = "TEST SUITE"
    ROBOT_LIBRARY_VERSION = VERSION
    DFLT_TIMEOUT = 0
    PIXEL_RATIO = 0.0

    def __init__(
        self,
        reference_folder=None,
        screenshot_folder=None,
        keyword_on_failure="ImageHorizonLibrary.Take A Screenshot",
        confidence=float("nan"),  #TODO: Clarification: will be set to 0.99 if cv is available
        strategy="default",
        edge_sigma=None, #TODO: cannot work with default setting
        edge_low_threshold=None, # TODO: cannot work with default setting
        edge_high_threshold=None, # TODO: cannot work with default setting
        edge_preprocess=None,
        edge_kernel_size=3,
        validate_match=False,
        validation_margin=5,
        scale_enabled=False,
        track_mode = False,
        hot_reload=False,
    ):
        """ImageHorizonLibrary can be imported with several options.

        ``reference_folder`` is path to the folder where all reference images
        are stored. It must be a _valid absolute path_. As the library
        is suite-specific (ie. new instance is created for every suite),
        different suites can have different folders for it's reference images.

        ``screenshot_folder`` is path to the folder where screenshots are
        saved. If not given, screenshots are saved to the current working
        directory.

        ``keyword_on_failure`` is the keyword to be run, when location-related
        keywords fail. If you wish to not take screenshots, use for example
        `BuiltIn.No Operation`. Keyword must however be a valid keyword.

        ``strategy`` sets the way how images are detected on the screen. See also
        keyword `Set Strategy` to change the strategy during the test. Parameters:
        - ``default`` - (Default)
        - ``edge`` - Advanced image recognition options with canny edge detection

        The ``edge`` strategy allows these additional parameters:
          - ``edge_sigma`` – standard deviation of the Gaussian blur applied
            before edge extraction; larger values smooth more noise (auto if
            ``None``).
          - ``edge_low_threshold`` – lower gradient magnitude threshold
            (0.0–1.0); gradients below this value are discarded (auto if
            ``None``).
          - ``edge_high_threshold`` – upper gradient magnitude threshold
            (0.0–1.0) used to mark strong edges; values between the thresholds
            are kept only if connected to a strong edge (auto if ``None``).
          - ``edge_preprocess`` – optional pre-processing filter; allowed
            filters ``gaussian`` (extra blur), ``median`` (noise reduction),
            ``erode`` (shrink bright regions), ``dilate`` (expand bright
            regions). Requires OpenCV ``cv2``.
          - ``edge_kernel_size`` – kernel size for the pre-processing filter
          - ``validate_match`` - re-check match on original image with OpenCV
          - ``validation_margin`` - margin in pixels around match for validation

        ``hot_reload`` rebuilds the reference image lookup before image-based
        keywords resolve an image name. This is useful when reference images
        are created, deleted or replaced while a suite is running.
        """

        # _RecognizeImages.set_strategy(self, strategy)
        #self.reference_folder = reference_folder
        self.reference_folder = (
            []
            if reference_folder is None
            else self.__evaluate_reference_folder(reference_folder)
        )
        self.screenshot_folder = screenshot_folder
        self.keyword_on_failure = keyword_on_failure
        self.open_applications = OrderedDict()
        self.screenshot_counter = 1
        self.is_windows = utils.is_windows()
        self.is_mac = utils.is_mac()
        self.is_linux = utils.is_linux()
        self.has_retina = utils.has_retina()
        self.has_cv = utils.has_cv()
        self.confidence = 0.99 if math.isnan(confidence) else confidence
        self.initial_confidence = self.confidence
        self._class_bases = inspect.getmro(self.__class__)
        self.set_strategy(
            strategy,
            edge_sigma=edge_sigma,
            edge_low_threshold=edge_low_threshold,
            edge_high_threshold=edge_high_threshold,
            confidence=self.confidence,
            edge_preprocess=edge_preprocess,
            edge_kernel_size=edge_kernel_size,
            validate_match=validate_match,
            validation_margin=validation_margin,
        )
        ### TODO: This hides an annoying error, rather let the processing fail ### 
        try:
            self.edge_sigma = float(edge_sigma) if edge_sigma is not None else None
        except (TypeError, ValueError):
            self.edge_sigma = None
        try:
            self.edge_low_threshold = (
                float(edge_low_threshold) if edge_low_threshold is not None else None
            )
        except (TypeError, ValueError):
            self.edge_low_threshold = None
        try:
            self.edge_high_threshold = (
                float(edge_high_threshold) if edge_high_threshold is not None else None
            )
        except (TypeError, ValueError):
            self.edge_high_threshold = None
        self.edge_preprocess = edge_preprocess
        try:
            self.edge_kernel_size = int(edge_kernel_size)
        except (TypeError, ValueError):
            self.edge_kernel_size = 3
        self.validate_match = validate_match
        try:
            self.validation_margin = int(validation_margin)
        except (TypeError, ValueError):
            self.validation_margin = 5

        # multi-scale search configuration
        self.scale_enabled = scale_enabled
        self.scale_min = 0.8
        self.scale_max = 1.2
        self.scale_steps = 9
        #super.__init__(reference_folder)


        self.look_up_table = self.__create_look_up_table()
        self.track_mode = track_mode
        self.hot_reload_enabled = self.__to_bool(hot_reload, "hot_reload")

    def __create_look_up_table(self):
        if self.reference_folder is None:
            raise PathNotSetException
        self.__check_required_type(self.reference_folder)
        look_up_table = {}
        if isinstance(self.reference_folder, list):
            for path in self.reference_folder:
                self._fill_look_up(look_up_table, path)
        else:
            self._fill_look_up(look_up_table, self.reference_folder)
        return look_up_table

    def __evaluate_reference_folder(self, reference_folder) -> List[str]:
        ## Check if passed value is either string or List
        image_path_type: Type[list|str|Path] = self.__check_required_type(reference_folder)
        self.__check_paths(image_path_type, reference_folder)
        self.reference_folder=  self.__update_reference_folder(image_path_type, reference_folder)
        return self.reference_folder

    def __update_reference_folder(self,image_path_type, reference_folder):
        if image_path_type is list:
            self.reference_folder = [str(ref) for ref in reference_folder]
        else:
            self.reference_folder = [str(reference_folder)]
        return self.reference_folder

    @staticmethod
    def _fill_look_up(look_up_table: dict, path: Path | str | List[str]):
        current_path_files = list(Path(path).resolve(strict=True).glob("*.png"))
        for current_path_file in current_path_files:
            png_name = current_path_file.stem  ## TODO: Check if it does what yo hope for -->replaced .name for .stem
            if png_name in look_up_table:
                current_png_path = look_up_table[png_name]
                LOGGER.warn(
                    f" You are replacing the '{png_name}' in path '{current_path_file.parent}'"
                    + ""
                    f" with the {png_name} from path '{current_png_path}'"
                )
            look_up_table[png_name] = str(current_path_file)

    def __check_paths(self, image_path_type: Type[list | str |Path], reference_folder: Path):
        if image_path_type is str or image_path_type is Path:
            if not Path(str(reference_folder)).is_dir():
                raise ValueError(self.__not_a_directory(reference_folder))
        else:
            for _, ref in enumerate(reference_folder):
                if not Path(str(ref)).is_dir():
                    raise ValueError(self.__not_a_directory(reference_folder))
        return True

    def __check_required_type(self, new_reference) -> Type[list | str]:
        if isinstance(new_reference, list):
            return list
        elif isinstance(new_reference, str):
            return str
        elif isinstance(new_reference, Path):
            return Path
        else:
            raise TypeError(
                f"reference must either be from type 'list' or 'str' not '{type(new_reference)}'"
            )

    def __not_a_directory(self, reference_folder):
        return f"'{reference_folder}' is not a directory!"

    def set_strategy(
        self,
        strategy,
        edge_sigma=None,
        edge_low_threshold=None,
        edge_high_threshold=None,
        confidence=None,
        edge_preprocess=None,
        edge_kernel_size=3,
        validate_match=False,
        validation_margin=5,
    ):
        """Changes the way how images are detected on the screen. This can also be done globally during `Importing`.
        Strategies:
        - ``default``
        - ``edge`` - Advanced image recognition options with canny edge detection

        The ``edge`` strategy allows these additional parameters:
          - ``edge_sigma`` - Gaussian blur intensity (auto if ``None``)
          - ``edge_low_threshold`` - low pixel gradient threshold (auto if ``None``)
          - ``edge_high_threshold`` - high pixel gradient threshold (auto if ``None``)
          - ``edge_preprocess`` - optional pre-processing filter; allowed filters:
            ``gaussian``, ``median``, ``erode``, ``dilate`` (requires OpenCV ``cv2``)
          - ``edge_kernel_size`` - kernel size for the pre-processing filter
          - ``validate_match`` - re-check match on original image with OpenCV
          - ``validation_margin`` - margin in pixels around match for validation

        Both strategies can optionally be initialized with a new confidence."""

        self.strategy = strategy
        if strategy == "default":
            self.strategy_instance = _StrategyPyautogui(self)
        elif strategy == "edge":
            self.strategy_instance = _StrategyCv2(self)
            try:
                self.edge_sigma = float(edge_sigma) if edge_sigma is not None else None
            except (TypeError, ValueError):
                self.edge_sigma = None
            try:
                self.edge_low_threshold = (
                    float(edge_low_threshold) if edge_low_threshold is not None else None
                )
            except (TypeError, ValueError):
                self.edge_low_threshold = None
            try:
                self.edge_high_threshold = (
                    float(edge_high_threshold) if edge_high_threshold is not None else None
                )
            except (TypeError, ValueError):
                self.edge_high_threshold = None
            self.edge_preprocess = edge_preprocess
            try:
                self.edge_kernel_size = int(edge_kernel_size)
            except (TypeError, ValueError):
                self.edge_kernel_size = 3
            self.validate_match = validate_match
            try:
                self.validation_margin = int(validation_margin)
            except (TypeError, ValueError):
                self.validation_margin = 5
        else:
            raise StrategyException('Invalid strategy: "%s"' % strategy)

        if not confidence is None:
            self.set_confidence(confidence)

        # Linking protected _try_locate to the strategy's method
        self._try_locate = self.strategy_instance._try_locate

    def _get_location(self, direction, location, offset):
        x, y = location[:2]
        offset = int(offset)
        if direction == "left":
            x = x - offset
        if direction == "up":
            y = y - offset
        if direction == "right":
            x = x + offset
        if direction == "down":
            y = y + offset
        return x, y

    def _click_to_the_direction_of(
        self, direction, location, offset, clicks, button, interval
    ):
        x, y = self._get_location(direction, location, offset)
        try:
            clicks = int(clicks)
        except ValueError:
            raise MouseException('Invalid argument "%s" for `clicks`')
        if button not in ["left", "middle", "right"]:
            raise MouseException('Invalid button "%s" for `button`')
        try:
            interval = float(interval)
        except ValueError:
            raise MouseException('Invalid argument "%s" for `interval`')

        LOGGER.info(
            "Clicking %d time(s) at (%d, %d) with "
            "%s mouse button at interval %f" % (clicks, x, y, button, interval)
        )
        ag.click(x, y, clicks=clicks, button=button, interval=interval)

    def _convert_to_valid_special_key(self, key):
        key = str(key).lower()
        if key.startswith("key."):
            key = key.split("key.", 1)[1]
        elif len(key) > 1:
            return None
        if key in ag.KEYBOARD_KEYS:
            return key
        return None

    def _validate_keys(self, keys):
        valid_keys = []
        for key in keys:
            valid_key = self._convert_to_valid_special_key(key)
            if not valid_key:
                raise KeyboardException(
                    'Invalid keyboard key "%s", valid '
                    "keyboard keys are:\n%r" % (key, ", ".join(ag.KEYBOARD_KEYS))
                )
            valid_keys.append(valid_key)
        return valid_keys

    def _press(self, *keys, **options):
        keys = self._validate_keys(keys)
        ag.hotkey(*keys, **options)

    @contextmanager
    def _tk(self):
        tk = TK()
        yield tk.clipboard_get()
        tk.destroy()

    def copy(self):
        """Copy currently selected text to the system clipboard.

        The platform specific shortcut is used (``Ctrl+C`` on Windows/Linux,
        ``⌘+C`` on macOS) and the clipboard content is returned.

        Returns
        -------
        str
            The text retrieved from the clipboard after the copy operation.
        """
        key = "Key.command" if self.is_mac else "Key.ctrl"
        self._press(key, "c")
        return self.get_clipboard_content()

    def get_clipboard_content(self):
        """Return the current text from the system clipboard.

        Returns
        -------
        str
            Contents of the clipboard.
        """
        with self._tk() as clipboard_content:
            return clipboard_content

    def pause(self):
        """Display a modal dialog to temporarily halt test execution.

        The dialog must be dismissed manually by clicking the Continue button.
        This is primarily intended for debugging or developing test cases.
        """
        ag.alert(text="Test execution paused.", title="Pause", button="Continue")

    def _run_on_failure(self):
        default ="""
        <h2> Image Not Found!
        <img scr='' alt='Image of the error resulting screenshot'>Image was not found<img/>
        <h2/>
                """ 
        try: 
            img = ag.screenshot("./not_found.png")
            image_path = str(Path(img)).resolve()
            default.replace("src=''", f"src='{image_path}'")
            LOGGER.error(default)
            print("went through")
        except Exception:
            pass
        # if not self.keyword_on_failure:
        #     return
        # try:
        #     BuiltIn().run_keyword(self.keyword_on_failure)
        # except Exception as e:
        #     LOGGER.debug(e)
        #     LOGGER.warn("Failed to take a screenshot. " "Is Robot Framework running?")

    def set_keyword_on_failure(self, keyword_on_failure):
        """Sets the keyword to run when location-related keywords fail.

        Can be used to change the failure behaviour during a test. Use
        ``BuiltIn.No Operation`` or ``None`` to disable screenshots temporarily
        and call this keyword again later to restore them.

        See `library importing` for usage of ``keyword_on_failure``.
        """
        self.keyword_on_failure = keyword_on_failure


    def set_reference_folder(self, new_reference: Union[List[str], str]) -> None:
        """
        Description: Replaces the current reference folder(s) with a new one. This action rebuilds the internal
        lookup table.

        Parameters:
        new_reference: A string or a list of strings representing the new directory path(s).

        Behavior:
        Performs the same validation as the __init__ method.
        Raises TypeError or ValueError on invalid input.
        Example:
            Set Reference Folder    C:\\project\\images
            Set Reference Folder    ${CURDIR}/images_v2
            Set Reference Folder    ${list_of_image_paths}
        """
        self.reference_folder = self.__evaluate_reference_folder(new_reference)
        self.look_up_table = self.__create_look_up_table()

    def add_reference_folder(self, new_reference: Union[List[str], str, Path]) -> None:
        if isinstance(new_reference, list) or  isinstance(new_reference, str) or isinstance(new_reference, Path):
            #if isinstance(self.reference_folder, str):  # self.reference_folder is a list of strings?
            #    tmp = self.reference_folder.split() # error-prone -> user has to make sure paths are separated via spaces
            #    tmp.extend(new_reference) if isinstance(
            #        new_reference, list
            #    ) else tmp.append(new_reference)
            #else:
            tmp = self.reference_folder
            tmp.extend(new_reference) if isinstance(
            new_reference, list) else tmp.append(new_reference)
            try:
                self.reference_folder = self.__evaluate_reference_folder(tmp)
            except ValueError:
                raise ValueError("There are invalid PATHS in your passed argument!")
            self.look_up_table = self.__create_look_up_table()
        else:
            raise TypeError(
                f"reference must either be from type 'list' or 'str' not '{type(new_reference)}'"
            )

    def set_screenshot_folder(self, screenshot_folder_path):
        """Sets the folder where screenshots are saved to.

        See `library importing` for more specific information.
        """
        self.screenshot_folder = screenshot_folder_path

    def set_track_mode(self, enabled=True):
        """Enable or disable track mode during test execution.

        When track mode is enabled, image-location keywords save the screenshot
        used for matching as ``track_mode-N.png`` in ``screenshot_folder`` or
        in the current working directory when no screenshot folder is set.

        ``enabled`` accepts booleans and common Robot Framework truthy/falsey
        strings such as ``true``, ``false``, ``yes``, ``no``, ``1`` and ``0``.
        """
        self.track_mode = self.__to_bool(enabled, "enabled")
        return self.track_mode

    def enable_track_mode(self):
        """Enable track mode during test execution."""
        return self.set_track_mode(True)

    def disable_track_mode(self):
        """Disable track mode during test execution."""
        return self.set_track_mode(False)

    def hot_reload(self, enabled=True):
        """Enable or disable automatic reference image lookup refresh.

        When hot reload is enabled, image-location keywords rebuild the
        reference image lookup table before resolving the requested image. This
        lets tests use reference images that are added, removed or replaced
        after the library has already been imported.

        ``enabled`` accepts booleans and common Robot Framework truthy/falsey
        strings such as ``true``, ``false``, ``yes``, ``no``, ``1`` and ``0``.
        """
        self.hot_reload_enabled = self.__to_bool(enabled, "enabled")
        return self.hot_reload_enabled

    def enable_hot_reload(self):
        """Enable automatic reference image lookup refresh."""
        return self.hot_reload(True)

    def disable_hot_reload(self):
        """Disable automatic reference image lookup refresh."""
        return self.hot_reload(False)

    def refresh_reference_images(self):
        """Rebuild the reference image lookup table immediately."""
        self.look_up_table = self.__create_look_up_table()
        return self.look_up_table

    @staticmethod
    def __to_bool(value, argument_name):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(int(value))
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "y", "on"):
                return True
            if normalized in ("false", "0", "no", "n", "off", "none"):
                return False
        raise ValueError('Invalid argument "%s" for `%s`' % (value, argument_name))

    def reset_confidence(self):
        """Resets the confidence level to the library default.
        If no confidence was given during import, this is None."""
        LOGGER.info("Resetting confidence level to {}.".format(self.initial_confidence))
        self.confidence = self.initial_confidence

    def set_confidence(self, new_confidence):
        """Sets the accuracy when finding images.

        ``new_confidence`` is a decimal number between 0 and 1 inclusive.

        See `Confidence level` about additional dependencies that needs to be
        installed before this keyword has any effect.
        """
        if new_confidence is not None:
            try:
                new_confidence = float(new_confidence)
                if not 1 >= new_confidence >= 0:
                    LOGGER.warn(
                        "Unable to set confidence to {}. Value "
                        "must be between 0 and 1, inclusive.".format(new_confidence)
                    )
                else:
                    self.confidence = new_confidence
            except (TypeError, ValueError):
                LOGGER.warn("Can't set confidence to {}".format(new_confidence))
        else:
            self.confidence = None

    def set_scale_range(self, scale_min=0.8, scale_max=1.2, scale_steps=9):
        """Enables searching images across a range of scales.

        When this keyword is used, the library tests multiple scaling factors
        between ``scale_min`` and ``scale_max``. ``scale_steps`` defines the
        number of values between those limits. Without calling this keyword,
        only a scale of ``1.0`` is considered during image search.
        """
        try:
            self.scale_min = float(scale_min)
            self.scale_max = float(scale_max)
            self.scale_steps = int(scale_steps)
            if self.scale_steps < 1 or self.scale_min <= 0 or self.scale_max <= 0:
                raise ValueError
            self.scale_enabled = True
        except (TypeError, ValueError):
            LOGGER.warn(
                "Invalid scale range: min=%s max=%s steps=%s" % (
                    scale_min, scale_max, scale_steps
                )
            )

    def reset_scale_range(self):
        """Disables multi-scale search and resets to defaults."""
        self.scale_enabled = False
        self.scale_min = 0.8
        self.scale_max = 1.2
        self.scale_steps = 9

    def _check_and_locate(self, reference_image, timeout=0, log_it=True):
        self._check_path_set()
        return self._locate_image(reference_image, timeout=timeout, log_it=log_it)


    def wait_for(self, reference_image, timeout=10, log_it=True):
        """Wait until an image appears on the screen.

        Parameters
        ----------
        reference_image : str
            Name of the reference image to locate.
        timeout : float, optional
            Maximum number of seconds to wait. Defaults to ``10``.

        Returns
        -------
        tuple
            Tuple ``(x, y, score, scale)`` describing the match.

        Raises
        ------
        ImageNotFoundException
            If the image is not found within the timeout.
        """
        stop_time = time() + float(timeout)
        location = None
        # last_exc = None
        self.__refresh_reference_images_if_needed()
        normalized_reference_image: str = self.__normalize_reference_image(reference_image)
        reference_path = self.__check_reference_image(normalized_reference_image)
        with self._suppress_keyword_on_failure():
            while True:
                try:
                    location = self._check_and_locate(reference_path, timeout=0, log_it=True)
                    break
                #except (
                    # InvalidImageException, # Replace with ImageNotInPathException
                    # ReferenceFolderException,  is covered ealier
                    # StrategyException,  # why here
                    # ScreenshotFolderException, # why here?
                #):
                    # These indicate a permanent misconfiguration and should not
                    # be retried within this loop.
                #    raise
                except ImageNotFoundException as e:
                    last_exc = e
                    if time() > stop_time:
                        break
                    sleep(0.1)
                except Exception as e:
                    if not _is_pyautogui_image_not_found(e):
                        raise
                    last_exc = e
                    if time() > stop_time:
                        break
                    sleep(0.1)
        if location is None:
            self.__raise_image_not_found_error(reference_image, None)  # need to think about that
        x, y, score, scale = location
        LOGGER.info(
            'Image "%s" found at %r (score %.3f, scale %.2f)'
            % (
                reference_image,
                (x, y),
                score if score is not None else float('nan'),
                scale,
            )
        )
        return location
    
    def __raise_image_not_found_error(self, reference_image, best_score):
        #confidence = getattr(self, "confidence", None)
        matches = 0
        best_score if best_score is not None else float('nan'),
        self.confidence if self.confidence is not None else float('nan'),
        #if log_it:
        best_match = f"Image '{self.strategy}' was not found on screen. "\
        f"(strategy: {self.strategy}, matches: {matches}, best score {best_score}, confidence {self.confidence}"
            # % (
            #     reference_image,
            #     self.strategy,
            #     matches,
            #     best_score if best_score is not None else float('nan'),
            #     self.confidence if self.confidence is not None else float('nan'),
            # )
        #print(best_match)
        LOGGER.info(
            best_match
        )
        self._run_on_failure()
        raise ImageNotFoundException(
            reference_image,
            matches=matches,
            best_score=best_score,
            confidence=self.confidence,
        )


    def _locate_all(self, reference_image, haystack_image=None):
        """Locate all occurrences of a reference image.

        Parameters
        ----------
        reference_image : str
            Name or path of the image to search for.
        haystack_image : array-like, optional
            Pre-captured screenshot to search in. If ``None``, a new screenshot
            of the screen is taken.

        Returns
        -------
        list[tuple]
            A list of tuples ``(location, score, scale)`` for each match. The
            list may be empty if no matches are found.

        Raises
        ------
        InvalidImageException
            If ``reference_image`` resolves to multiple files.
        """
       # reference_images = self._get_reference_images(reference_image)
       # if len(reference_images) > 1:
        #    raise InvalidImageException(
        #        f'Locating ALL occurences of MANY files ({", ".join(reference_images)}) is not supported.'
        #    )
        self.__refresh_reference_images_if_needed()
        normalized_name = self.__normalize_reference_image(reference_image)
        self.__check_reference_image(self.__normalize_reference_image(reference_image))
        ref_image_path = self.look_up_table[normalized_name]
        locations = self._try_locate(
            ref_image_path, locate_all=True, haystack_image=haystack_image
        )
        return locations


    def does_exist(self, reference_image):
        """Check whether a reference image exists on the screen.

        Parameters
        ----------
        reference_image : str
            Name of the reference image to locate.

        Returns
        -------
        bool
            ``True`` if the image was found, ``False`` otherwise. The keyword
            never raises an exception.
        """
        with self._suppress_keyword_on_failure():
            try:
                self.wait_for(reference_image, timeout=0, log_it=True)
                return True
            except ImageNotFoundException:
                return False
            except Exception as e:
                if _is_pyautogui_image_not_found(e):
                    return False
                raise


    def locate_all(self, reference_image):
        """Locate all occurrences of an image on screen.

        Parameters
        ----------
        reference_image : str
            Name or path of the image to locate.

        Returns
        -------
        list[tuple]
            List of tuples ``(x, y, score, scale)`` describing each match.

        Raises
        ------
        InvalidImageException
            If ``reference_image`` resolves to multiple files.
        """
        matches = []
        locations = self._locate_all(reference_image)
        if self.PIXEL_RATIO == 0.0:
            self.get_pixel_ratio()
        for loc, score, scale in locations:
            center = ag.center(loc)
            x, y = center.x, center.y
            if self.PIXEL_RATIO > 1:
                x = x / self.PIXEL_RATIO
                y = y / self.PIXEL_RATIO
            matches.append((x, y, score, scale))
        return matches


    def _check_path_set(self) -> None:
        if not self.get_reference_folder():
            raise PathNotSetException


    def click_image(self, reference_image, timeout=DFLT_TIMEOUT):
        location = self.wait_for(reference_image, timeout=timeout)
        # location = self._check_and_locate(image_name, timeout=timeout)
        ag.click(location)
        return location


    def locate(self, reference_image, timeout=DFLT_TIMEOUT, log_it=True):
        location = self.wait_for(reference_image, timeout=timeout)
        return location


    def click(self, button: str = "left"):
        ag.click(button=button)


    def click_to_the_left_of_image(
            self, reference_image, offset, clicks, button="left", interval=0.0
    ):
        x, y, score, scale = self.wait_for(reference_image, timeout=0)
        location = (x,y)
        new_location = self._change_coordinates_of_location(location, x=-abs(int(offset)))
        updated_location = new_location[0], new_location[1], score, scale
        ag.click(new_location, clicks=int(clicks), button=button, interval=interval)
        return updated_location


    def click_to_the_right_of_image(
            self, reference_image, offset, clicks, button="left", interval=0.0
    ):
        x, y, score, scale = self.wait_for(reference_image, timeout=0)
        location = (x,y)
        new_location = self._change_coordinates_of_location(location, x=abs(int(offset)))
        updated_location = new_location[0], new_location[1], score, scale
        ag.click(new_location, clicks=int(clicks), button=button, interval=interval)
        return updated_location


    def click_to_the_above_of_image(
            self, reference_image, offset, clicks, button="left", interval=0.0
    ):
        x, y, score, scale = self.wait_for(reference_image, timeout=0)
        location = (x,y)
        new_location = self._change_coordinates_of_location(location, y=-abs(int(offset)))
        updated_location = new_location[0], new_location[1], score, scale
        ag.click(new_location, clicks=int(clicks), button=button, interval=interval)
        return updated_location


    def click_to_the_below_of_image(
            self, reference_image, offset, clicks, button="left", interval=0.0
    ):
        x, y, score, scale = self.wait_for(reference_image, timeout=0)
        location = (x,y)
        new_location = self._change_coordinates_of_location(location, y=abs(int(offset)))
        updated_location = new_location[0], new_location[1], score, scale
        ag.click(new_location, clicks=int(clicks), button=button, interval=interval)
        return updated_location

    def __check_reference_image(self, reference_image):
        if reference_image in self.look_up_table:
            return self.look_up_table[reference_image]
        else:
            raise ImageNotInPath(reference_image, self.look_up_table)

    def __refresh_reference_images_if_needed(self):
        if self.hot_reload_enabled:
            self.refresh_reference_images()

    @staticmethod
    def __normalize_reference_image(reference_image: str):
        # type error if not a string
        return reference_image.lower().replace(" ", "").replace(".png","")


    def _change_coordinates_of_location(self, location, x=0, y=0) -> Tuple[int]:
        new_x, new_y  = location[0] + x, location[0] + y
        return (new_x, new_y)
