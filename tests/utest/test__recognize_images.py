from unittest import TestCase
from unittest.mock import Mock, patch
from PIL import Image, ImageTk
import tkinter as tk
import time
from pathlib import Path
import ImageHorizonLibrary
from robot.utils.asserts import assert_raises
from ImageHorizonLibrary import ImageHorizonLibrary as ihl
from ImageHorizonLibrary.errors import ImageNotFoundException



class TestRecognizeImages(TestCase):
     

     def setUp(self):
        self.default_path = Path(__file__).resolve().parent / "reference_images"
        self.new_set_path = Path(__file__).resolve().parent / "rëförence_imägës"
        self.my_picture_path = self.default_path / "my_picture.png"
        self.current_frame = self.default_path / "current_frame.png"


     def build_tk_app(self, runner, offset=None, click_count=None):
        # 1. Setup the "Projector" window
        root = tk.Tk()

        # Position the window at x=200, y=200
        root.geometry("+200+200")
        root.overrideredirect(True)  # Removes window borders/title bar

        container_frame = tk.Frame(root, padx=10, pady=10, highlightbackground="blue", highlightthickness=2)
        container_frame.pack()
        # Load your needle image
        img = Image.open(self.my_picture_path).convert("RGB")
        tk_img = ImageTk.PhotoImage(img)

        label = tk.Label(container_frame, image=tk_img, bg='white')
        label.pack()

        button = tk.Button(container_frame, text="hello")
        #button.bind('<Button-1>', hello)
        button.pack()

        # Force the window to draw on the Xvfb display
        root.update()

        # 2. Give the OS a split second to actually render the pixels
        time.sleep(0.5)

        try:
            # 3. EXECUTION: Now pyautogui looks at the VIRTUAL SCREEN
            # This is the "real" test of locateCenterOnScreen
            if offset and click_count:
                coords = runner("my_picture.png", offset, click_count)
            else:
                coords = runner("my_picture.png")
            print(f"coords: {coords}")
            # 4. ASSERTION
            assert coords is not None
            print(f"Found at: {coords}")
        finally:
            root.destroy()  # Close the window

class TestRecognizeImagesWrongConfigs(TestRecognizeImages):

    def setUp(self):
        super().setUp()
        self.ih_lib = ihl()
        
        
        
    def test_click_image(self):
        click_image = self.ih_lib.click_image
        with self.assertRaises(ImageNotFoundException):
            self.build_tk_app(click_image)

class TestRecognizeImagesTrackMode(TestRecognizeImages):
    def setUp(self):
        super().setUp()
        self.ih_lib = ihl(reference_folder=self.default_path, track_mode=True)

    def test_click_image(self):
        click_image = self.ih_lib.click_image
        # Is there some pictures to delete afterwards?
        self.build_tk_app(click_image)
        



class TestRecognizeImagesHappyPath(TestRecognizeImages):
    def setUp(self):
        super().setUp()
        print(f"default_path: {self.default_path}")
        self.ih_lib = ihl(reference_folder=self.default_path, confidence=0.99)   # confidence none is a problem
        print(f"get_default_path: {self.ih_lib.get_reference_folder()}")
        self.ih_lib.set_reference_folder(self.default_path)
        ag = Mock()
        ag.lock.return_value = (1,1)

        pass

    def build_tk_app(self, runner, offset=None, click_count=None):
        # 1. Setup the "Projector" window
        root = tk.Tk()

        # Position the window at x=200, y=200
        root.geometry("+200+200")
        root.overrideredirect(True)  # Removes window borders/title bar

        container_frame = tk.Frame(root, padx=10, pady=10, highlightbackground="blue", highlightthickness=2)
        container_frame.pack()
        # Load your needle image
        img = Image.open(self.my_picture_path).convert("RGB")
        tk_img = ImageTk.PhotoImage(img)

        label = tk.Label(container_frame, image=tk_img, bg='white')
        label.pack()

        button = tk.Button(container_frame, text="hello")
        #button.bind('<Button-1>', hello)
        button.pack()

        # Force the window to draw on the Xvfb display
        root.update()

        # 2. Give the OS a split second to actually render the pixels
        time.sleep(0.5)

        try:
            # 3. EXECUTION: Now pyautogui looks at the VIRTUAL SCREEN
            # This is the "real" test of locateCenterOnScreen
            if offset and click_count:
                coords = runner("my_picture.png", offset, click_count)
            else:
                coords = runner("my_picture.png")
            print(f"coords: {coords}")
            # 4. ASSERTION
            assert coords is not None
            print(f"Found at: {coords}")
        finally:
            root.destroy()  # Close the window
    



    def test__suppress_keyword_on_failure(self):
        self.fail()

    def test_get_reference_folder(self):
        expected = self.default_path
        self.assertListEqual([str(expected)], self.ih_lib.reference_folder)

    def test_set_reference_folder(self):
        expected = self.new_set_path.resolve()
        self.ih_lib.set_reference_folder(str(expected))
        self.assertListEqual([str(expected)], self.ih_lib.reference_folder)

    def test_add_reference_folder(self):
        expected = [str(self.default_path), str(self.new_set_path)]
        self.ih_lib.add_reference_folder(str(self.new_set_path))
        self.assertListEqual(expected, self.ih_lib.reference_folder)

    def test__fill_look_up(self):
        self.fail()

    def test_wait_for(self):
        self.ih_lib.set_reference_folder(str(self.default_path))
        wait_for = self.ih_lib.wait_for
        self.build_tk_app(wait_for)
        #self.fail()

    def test__locate_all(self):
        self.ih_lib.set_reference_folder(str(self.default_path))
        locate_all = self.ih_lib.locate_all
        self.build_tk_app(locate_all)
        #self.fail()

    def test_does_exist(self):
        self.ih_lib.set_reference_folder(str(self.default_path))
        does_exist = self.ih_lib.does_exist
        self.build_tk_app(does_exist)
        #self.fail()

    def test_locate_all(self):
        self.fail()

    def test__check_path_set(self):
        self.fail()

    #@mark("click_image")
    def test_click_image(self):
        self.ih_lib.set_reference_folder(str(self.default_path))
        click_image = self.ih_lib.click_image
        self.build_tk_app(click_image)

    def test_locate(self):
        self.ih_lib.set_reference_folder(str(self.default_path))
        locate = self.ih_lib.locate
        self.build_tk_app(locate)


    def test_click(self):
        # Create an simple application for click validation?
        self.fail()

    def test_click_to_the_left_of_image(self):
        self.ih_lib.set_reference_folder(str(self.default_path))
        loi = self.ih_lib.click_to_the_left_of_image
        self.build_tk_app(loi, 10, 1)
        #self.fail()

    def test_click_to_the_right_of_image(self):
        self.fail()

    def test_click_to_the_above_of_image(self):
        self.fail()

    def test_click_to_the_below_of_image(self):
        self.fail()

    @patch("ImageHorizonLibrary.ImageHorizonLibrary.locate")
    def test__raise_image_not_found_error(self, mock_locate):
        mock_locate.side_effects =ImageHorizonLibrary.errors.ImageNotFoundException
        assert_raises(ImageHorizonLibrary.errors.ImageNotInPath,self.ih_lib.locate("s Picture"))

    def test_debug_image(self):
        self.fail()
