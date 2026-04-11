from unittest import TestCase
from ImageHorizonLibrary.errors import ImageHorizonLibraryError, ImageNotFoundException, ImageNotInPath, InvalidImageException, PathNotSetException


class TestImageHorizonErrors(TestCase):


    def trigger_image_not_found(self, matches=None, best_score=None, confidence=None):
        with self.assertRaises(ImageNotFoundException) as e:
            raise  ImageNotFoundException("example.png", matches,best_score, confidence)
        
        self.assertRegex(str(e.exception), ".*")

    def  test_image_not_found_default(self):
        self.trigger_image_not_found()


    def test_image_found_matches_positive_matches_and_confidence(self):
        self.trigger_image_not_found(matches=1, confidence=0.99)

    def test_image_found_matches_best_score_and_confidence(self):
        self.trigger_image_not_found(best_score=0.999, confidence=0.99)

    def test_image_found_matches_best_score(self):
        self.trigger_image_not_found(best_score=0.999)


    def test_path_not_set(self):
        with self.assertRaises(PathNotSetException) as e:
            raise PathNotSetException
        self.assertRegex(str(e.exception), ".*")

    def test_image_not_in_path(self):
        with self.assertRaises(ImageNotInPath) as e:
            raise ImageNotInPath("image_name", "img/path")
        
        self.assertRegex(str(e.exception), ".*")

