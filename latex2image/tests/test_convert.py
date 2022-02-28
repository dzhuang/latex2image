import os
from unittest import TestCase, mock

from tests.base_test_mixins import get_latex_file_dir

from latex.converter import (ImageConvertError, LatexCompileError,
                             UnknownCompileError, get_tex2img_class,
                             tex_to_img_converter)
from latex.utils import file_read, get_abstract_latex_log


def get_file_content(file_path):
    return file_read(file_path)


class TexToImgConverterTest(TestCase):
    def test_xelatex_png(self):
        xelatex_doc_path = get_latex_file_dir("xelatex")
        for filename in os.listdir(xelatex_doc_path):
            file_path = os.path.join(xelatex_doc_path, filename)
            with self.subTest(filename=filename, test_name="xelatex"):
                tex_source = get_file_content(file_path).decode("utf-8")
                data_url = tex_to_img_converter(
                    "xelatex", tex_source, "png"
                ).get_converted_data_url()
                self.assertIsNotNone(data_url)
                self.assertTrue(data_url.startswith("data:image/png"))

    def test_lualatex_png(self):
        lualatex_doc_path = get_latex_file_dir("lualatex")
        for filename in os.listdir(lualatex_doc_path):
            file_path = os.path.join(lualatex_doc_path, filename)
            with self.subTest(filename=filename, test_name="lualatex"):
                tex_source = get_file_content(file_path).decode("utf-8")
                data_url = tex_to_img_converter(
                    "lualatex", tex_source, "png",
                ).get_converted_data_url()
                self.assertIsNotNone(data_url)
                self.assertTrue(data_url.startswith("data:image/png"))

    def test_pdfsvg(self):
        pdf2svg_doc_path = get_latex_file_dir("pdf2svg")
        for filename in os.listdir(pdf2svg_doc_path):
            file_path = os.path.join(pdf2svg_doc_path, filename)
            with self.subTest(filename=filename, test_name="xelatex_svg"):
                tex_source = get_file_content(file_path).decode("utf-8")
                data_url = tex_to_img_converter(
                    "xelatex", tex_source, "svg"
                ).get_converted_data_url()
                self.assertIsNotNone(data_url)
                self.assertTrue(data_url.startswith("data:image/svg"))

    def test_pdflatex(self):
        pdflatex_doc_path = get_latex_file_dir("pdflatex")
        for image_format in ["png", "svg"]:
            for filename in os.listdir(pdflatex_doc_path):
                file_path = os.path.join(pdflatex_doc_path, filename)
                with self.subTest(
                        filename=filename, test_name="pdflatex",
                        image_format=image_format):
                    tex_source = get_file_content(file_path).decode("utf-8")
                    data_url = tex_to_img_converter(
                        "pdflatex", tex_source, image_format,
                    ).get_converted_data_url()
                    self.assertIsNotNone(data_url)
                    self.assertTrue(data_url.startswith(
                        "data:image/%s" % image_format))

    def test_latex_png(self):
        latex_doc_path = get_latex_file_dir("latex2png")
        for image_format in ["png", "svg"]:
            for filename in os.listdir(latex_doc_path):
                file_path = os.path.join(latex_doc_path, filename)
                with self.subTest(
                        filename=filename, test_name="latex",
                        image_format=image_format):
                    tex_source = get_file_content(file_path).decode("utf-8")
                    data_url = tex_to_img_converter(
                        "latex", tex_source, image_format,
                    ).get_converted_data_url()
                    self.assertIsNotNone(data_url)
                    self.assertTrue(
                        data_url.startswith("data:image/%s" % image_format))

    def test_latex_png_tizk_got_svg(self):
        latex_doc_path = get_latex_file_dir("latex2png")
        for image_format in ["png"]:
            for filename in os.listdir(latex_doc_path):
                file_path = os.path.join(latex_doc_path, filename)
                with self.subTest(
                        filename=filename, test_name="latex",
                        image_format=image_format):
                    tex_source = get_file_content(file_path).decode("utf-8")
                    data_url = tex_to_img_converter(
                        "latex", tex_source, image_format,
                    ).get_converted_data_url()
                    self.assertIsNotNone(data_url)
                    self.assertTrue(data_url.startswith(
                        "data:image/%s" % image_format))

    def test_more_than_one_pages_error(self):
        latex_doc_path = get_latex_file_dir("pdflatex_multilple_pages")
        for filename in os.listdir(latex_doc_path):
            file_path = os.path.join(latex_doc_path, filename)
            image_format = "png"
            with self.subTest(
                    filename=filename, test_name="pdflatex",
                    image_format=image_format):
                tex_source = get_file_content(file_path).decode("utf-8")
                with self.assertRaises(ImageConvertError):
                    tex_to_img_converter(
                        "pdflatex", tex_source, image_format,
                    ).get_converted_data_url()

    def test_compile_error_no_log(self):
        doc_path = get_latex_file_dir("xelatex")
        filename = os.listdir(doc_path)[0]
        file_path = os.path.join(doc_path, filename)
        tex_source = get_file_content(file_path).decode("utf-8")

        expected_error = "some error"
        with mock.patch("latex.converter.Tex2ImgBase.compile_popen"
                        ) as mock_compile_subprocess:
            mock_compile_subprocess.return_value = ["foo", expected_error, 1]
            with self.assertRaises(LatexCompileError) as cm:
                tex_to_img_converter(
                    "xelatex", tex_source, "png"
                ).get_converted_data_url()
            self.assertIn(expected_error, str(cm.exception))

    def test_compile_no_error_but_no_compiled_pdf_file(self):
        doc_path = get_latex_file_dir("xelatex")
        filename = os.listdir(doc_path)[0]
        file_path = os.path.join(doc_path, filename)
        tex_source = get_file_content(file_path).decode("utf-8")

        with mock.patch("latex.converter.Tex2ImgBase.compile_popen"
                        ) as mock_compile_subprocess:
            mock_compile_subprocess.return_value = ["foo", "", 0]
            with self.assertRaises(UnknownCompileError) as cm:
                tex_to_img_converter(
                    "xelatex", tex_source, "png"
                ).get_converted_data_url()
            self.assertIn("No pdf file was generated.", str(cm.exception))

    def test_convert_error(self):
        doc_path = get_latex_file_dir("xelatex")
        filename = os.listdir(doc_path)[0]
        file_path = os.path.join(doc_path, filename)
        tex_source = get_file_content(file_path).decode("utf-8")

        expected_error = "some error"
        with mock.patch("latex.converter.ImageConverter.convert_popen"
                        ) as mock_compile_subprocess:
            mock_compile_subprocess.return_value = ["bar", expected_error, 1]
            with self.assertRaises(ImageConvertError) as cm:
                tex_to_img_converter(
                    "xelatex", tex_source, "svg"
                ).get_converted_data_url()
            self.assertIn(expected_error, str(cm.exception))

    def test_get_data_url_error(self):
        doc_path = get_latex_file_dir("xelatex")
        filename = os.listdir(doc_path)[0]
        file_path = os.path.join(doc_path, filename)
        tex_source = get_file_content(file_path).decode("utf-8")

        expected_error = "some error"
        with mock.patch("latex.converter.get_data_url") as mock_get_data_url:
            mock_get_data_url.side_effect = RuntimeError(expected_error)
            with self.assertRaises(ImageConvertError) as cm:
                tex_to_img_converter(
                    "xelatex", tex_source, "svg"
                ).get_converted_data_url()
            self.assertIn(expected_error, str(cm.exception))

    def test_imagemagick_convert_error(self):
        doc_path = get_latex_file_dir("xelatex")
        filename = os.listdir(doc_path)[0]
        file_path = os.path.join(doc_path, filename)
        tex_source = get_file_content(file_path).decode("utf-8")

        expected_error = "some ImageMagick error"
        with mock.patch("latex.converter.wand_image.convert") as mock_im_convert:
            mock_im_convert.side_effect = RuntimeError(expected_error)
            with self.assertRaises(ImageConvertError) as cm:
                tex_to_img_converter(
                    "xelatex", tex_source, "png"
                ).get_converted_data_url()
            self.assertIn(expected_error, str(cm.exception))

    def test_do_convert_success_but_no_images(self):
        doc_path = get_latex_file_dir("xelatex")
        filename = os.listdir(doc_path)[0]
        file_path = os.path.join(doc_path, filename)
        tex_source = get_file_content(file_path).decode("utf-8")

        with mock.patch("latex.converter.get_number_of_images") as mock_get_n_images:
            mock_get_n_images.return_value = 0
            with self.assertRaises(ImageConvertError) as cm:
                tex_to_img_converter(
                    "xelatex", tex_source, "png"
                ).get_converted_data_url()
            self.assertIn("No image was generated", str(cm.exception))


class GetTex2imgClassTest(TestCase):
    # test latex.converter.get_tex2img_class
    def test_compiler_not_allowed(self):
        with self.assertRaises(ValueError):
            get_tex2img_class("pdftex", "png")

    def test_not_allowed_compiler_format_combination(self):
        with mock.patch(
                "latex.converter.ALLOWED_LATEX2IMG_FORMAT", ['png', 'svg', 'jpg']):
            with self.assertRaises(ValueError):
                get_tex2img_class("pdflatex", "jpg")


class GetAbstractLatexLogTest(TestCase):
    # test latex.utils.get_abstract_latex_log
    def test_return_str(self):
        # no LATEX_LOG_OMIT_LINE_STARTS and LATEX_ERR_LOG_BEGIN_LINE_STARTS
        self.assertEqual(get_abstract_latex_log("abcd"), "abcd")
