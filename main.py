import base64
import json

from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer

# noinspection PyProtectedMember
from PIL import Image  # Pillow
from fitz import fitz, Document  # PyMuPDF
from PyPDF2 import PdfFileWriter, PdfFileReader  # PyPDF2
from luckydonaldUtils.encoding import to_binary as b  # luckydonald-utils


HTML = """
""".strip()

IMG_TYPE = 'png'


class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.do_stuff()
    # end def

    def do_GET(self):
        self.do_stuff()
    # end def

    def do_stuff(self):
        # Switch for the path
        if self.path == '/crop':
            # we got a json with the pdf, the page and coordinates to crop the pdf with.
            # Let's do that and return a cropped pdf.
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            data = {
                "coordinates": {
                    "width": 490,
                    "height": 693,
                    "left": 61,
                    "top": 87
                },
                "image": {
                    "width": 612,
                    "height": 866
                },
                "pdf": {
                    "page": 0,
                    "base64": "a4e45f4a245===",
                },
            }
            data = json.loads(data_string)

            pdf_data: str = data['pdf']['base64'].removeprefix('data:application/pdf;base64,')
            pdf_data: bytes = base64.decodebytes(pdf_data.encode())
            pdf_page = data['pdf']['page']

            img_w, img_h = data['image']['width'],  data['image']['height']
            select_w, select_h = data['coordinates']['width'],  data['coordinates']['height']
            select_l, select_t = data['coordinates']['left'],  data['coordinates']['top']

            percent_w = select_w / img_w
            percent_h = select_h / img_h
            percent_l = select_l / img_w
            percent_t = select_t / img_h

            fake_pdf_file = BytesIO(pdf_data)
            pdf_file = PdfFileReader(fake_pdf_file)
            page = pdf_file.getPage(pdf_page)
            print(page.cropBox.getUpperLeft())
            print(page.cropBox.getUpperRight())
            print(page.cropBox.getLowerLeft())
            print(page.cropBox.getLowerRight())
            # print(data)

            pdf_w, pdf_h = page.cropBox.getWidth(), page.cropBox.getHeight()
            pdf_l, pdf_t = page.cropBox.getUpperLeft()
            pdf_l, pdf_t, pdf_w, pdf_h = float(pdf_l), float(pdf_t), float(pdf_w), float(pdf_h)

            print(pdf_l, pdf_t, pdf_w, pdf_h)
            pdf_t = pdf_h - pdf_t  # needs to be inverted

            print(pdf_l, pdf_t, pdf_w, pdf_h)

            new_w = pdf_w * percent_w
            new_h = pdf_h * percent_h
            new_l = pdf_l + (pdf_w * percent_l)
            new_t = pdf_t + (pdf_h * percent_t)
            print(new_l, new_t, new_w, new_h)
            new_t = pdf_h - new_t  # needs to be inverted
            print(new_l, new_t, new_w, new_h)

            page.cropBox.upperLeft = (new_l, new_t)
            page.cropBox.lowerRight = (new_l + new_w, new_t - new_h)
            print(((new_l, new_t), (new_l + new_w, new_t - new_h)))

            print(page.cropBox.getUpperLeft())
            print(page.cropBox.getUpperRight())
            print(page.cropBox.getLowerLeft())
            print(page.cropBox.getLowerRight())

            output_file = BytesIO()

            output_pdf = PdfFileWriter()
            output_pdf.addPage(page)
            output_pdf.write(output_file)

            content_type = 'application/json'
            base64_data = base64.encodebytes(output_file.getvalue())
            base64_data = base64_data.replace(b'\n', b'')
            message = b'{"filename": "a.pdf", "base64": "' + base64_data + b'"}'
            fake_pdf_file.close()
            output_file.close()
        elif self.path == '/preview':
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            data = {
                "pdf": {
                    "page": 0,
                    "base64": "a4e45f4a245===",
                },
            }
            data = json.loads(data_string)

            pdf_data: str = data['pdf']['base64'].removeprefix('data:application/pdf;base64,')
            pdf_data: bytes = base64.decodebytes(b(pdf_data))
            pdf_page = data['pdf']['page']

            # https://stackoverflow.com/q/42733539/3423324#convert-pdf-page-to-image-with-pypdf2-and-bytesio
            # https://stackoverflow.com/a/54001356/3423324#how-to-render-a-pypdf-pageobject-page-to-a-pil-image
            doc: Document = fitz.open(stream=pdf_data, filetype='application/pdf')
            pdf_pages = doc.page_count
            pdf_page = min(max(0, pdf_page), pdf_pages - 1)  # make sure it's: 0 ≤ page < n

            page = doc.loadPage(pdf_page)
            pix = page.getPixmap()
            print(pix, len(pix.samples))
            mode = None
            if len(pix.samples) == 3 * pix.width * pix.height:
                mode = "RGB"
            elif len(pix.samples) == 4 * pix.width * pix.height:
                mode = "RGBA"
            # end if
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            fake_file = BytesIO()
            img.save(fake_file, IMG_TYPE)

            content_type = 'application/json'
            base64_data = base64.encodebytes(fake_file.getvalue())
            base64_data = base64_data.replace(b'\n', b'')
            message = (
                b'{"mime": "image/' + b(IMG_TYPE) + b'", "base64": "' + base64_data + b'", '
                b'"page": ' + b(str(pdf_page)) + b', "pages": ' + b(str(pdf_pages)) + b'}'
            )
            fake_file.close()
        else:
            if not HTML:
                with open('cropper.html') as f:
                    html = f.read()
                # end with
            else:
                html = HTML
            # end if

            content_type = 'text/html'
            message = bytes(html, "utf8")
        # end if

        self.protocol_version = "HTTP/1.1"
        self.send_response(200)
        self.send_header("Content-Length", str(len(message)))
        self.send_header("Content-Type", content_type)
        self.end_headers()

        self.wfile.write(message)
        return
    # end def
# end class


def run():
    server = ('', 80)
    httpd = HTTPServer(server, RequestHandler)
    httpd.serve_forever()
# end def


try:
    import pyto_ui as ui
    web_view = ui.WebView()
    web_view.load_html(html)

    from background import BackgroundTask # For running in background

    # Run the server in background
    with BackgroundTask() as b:
        run()
    # end if
except (ImportError, ModuleNotFoundError):
    run()
# end try

