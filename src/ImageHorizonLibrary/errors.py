# -*- coding: utf-8 -*-
class ImageHorizonLibraryError(ImportError):
    pass


class ImageNotFoundException(Exception):
    def __init__(
        self,
        image_name,
        matches=None,
        best_score=None,
        confidence=None,
    ):
        """Describe missing reference image with optional diagnostics.

        Parameters
        ----------
        image_name : str
            Name of the image that was not found.
        matches : int, optional
            Number of matches detected above the confidence threshold. Defaults
            to ``None``.
        best_score : float, optional
            Highest score returned by the matching algorithm.
        confidence : float, optional
            Confidence threshold used for the search.
        """

        self.image_name = image_name
        self.matches = matches
        self.best_score = best_score
        self.confidence = confidence

    def __str__(self):
        msg = 'Reference image "%s" was not found on screen' % self.image_name
        details = []
        if self.matches:
            details.append(f"matches found: {self.matches}")
        if self.best_score is not None and self.confidence is not None:
            details.append(
                f"best score {self.best_score:.2f} (confidence {self.confidence:.2f})"
            )
        elif self.best_score is not None:
            details.append(f"best score {self.best_score:.2f}")
        elif self.confidence is not None:
            details.append(f"confidence {self.confidence:.2f}")
        if details:
            msg += ". " + ", ".join(details)
        return msg


class InvalidImageException(Exception):
    pass


class KeyboardException(Exception):
    pass


class MouseException(Exception):
    pass


class OSException(Exception):
    pass


class ReferenceFolderException(Exception):
    pass


class ScreenshotFolderException(Exception):
    pass

class StrategyException(Exception):
    pass

class PathNotSetException(Exception):
    KEYWORD = ""
    PATH_NOT_SET = f"""This error occured most likey to the fact
                       that you tried to use the {KEYWORD} keyword without having a path set earlier.
                       Please use the 'Set Reference Keyword' or  during the import of the ImageHorizionNG
                       library pass a value to 'reference_folder' argument.
                    """

    def __str__(self):
        return  PathNotSetException
    
class ImageNotInPath(KeyError):
    def __init__(self, image_name, image_path):
        self.__image_name = image_name
        self.__image_path = image_path
    
    def __str__(self):
        return f"image '{self.__image_name}' was not found in path(s) {self.__image_path}"
