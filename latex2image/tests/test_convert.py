import os
from unittest import TestCase

from latex.converter import tex_to_img_converter, CommandBase, Latexmk, Pdf2svg
from latex.utils import file_read
from tests.base_test_mixins import get_latex_file_dir


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
                        filename=filename, test_name="pdflatex", image_format=image_format):
                    tex_source = get_file_content(file_path).decode("utf-8")
                    data_url = tex_to_img_converter(
                        "pdflatex", tex_source, image_format,
                    ).get_converted_data_url()
                    self.assertIsNotNone(data_url)
                    self.assertTrue(data_url.startswith("data:image/%s" % image_format))

    def test_latex_png(self):
        latex_doc_path = get_latex_file_dir("latex2png")
        for image_format in ["png", "svg"]:
            for filename in os.listdir(latex_doc_path):
                file_path = os.path.join(latex_doc_path, filename)
                with self.subTest(
                        ilename=filename, test_name="latex", image_format=image_format):
                    tex_source = get_file_content(file_path).decode("utf-8")
                    data_url = tex_to_img_converter(
                        "latex", tex_source, image_format,
                    ).get_converted_data_url()
                    self.assertIsNotNone(data_url)
                    self.assertTrue(data_url.startswith("data:image/%s" % image_format))

    def test_latex_png_tizk_got_svg(self):
        latex_doc_path = get_latex_file_dir("latex2png")
        for image_format in ["png"]:
            for filename in os.listdir(latex_doc_path):
                file_path = os.path.join(latex_doc_path, filename)
                with self.subTest(
                        ilename=filename, test_name="latex", image_format=image_format):
                    tex_source = get_file_content(file_path).decode("utf-8")
                    data_url = tex_to_img_converter(
                        "latex", tex_source, image_format,
                    ).get_converted_data_url()
                    self.assertIsNotNone(data_url)
                    self.assertTrue(data_url.startswith("data:image/%s" % image_format))


class VersionCheckTest(TestCase):
    def test_check_version_error(self):
        class FakeCommand1(CommandBase):
            name = "noneexist"
            cmd = "nonexist"

        fake_command = FakeCommand1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)

    def test_min_version_error(self):
        class FakeLatexmk1(Latexmk):
            min_version = "100.39"

        fake_command = FakeLatexmk1()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)

    def test_max_version_error(self):
        class FakeLatexmk2(Latexmk):
            max_version = "1.39"

        fake_command = FakeLatexmk2()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)

    def test_pdf2svg_with_version_check_error(self):
        # pdf2svg has no version.
        class FakePdf2svg(Pdf2svg):
            skip_version_check = False

        fake_command = FakePdf2svg()
        errors = fake_command.check()
        self.assertEqual(len(errors), 1)
