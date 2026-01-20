# archivo mandar_pdf.py

import fitz  # PyMuPDF en https://pymupdf.readthedocs.io/en/latest/installation.html  pip install --upgrade pymupdf
  # pip install PyMuPDF en https://medium.com/@vinitvaibhav9/extracting-pdf-highlights-using-python-9512af43a6d

# Abrir el archivo
def extraer_anotaciones_array(path_pdf):
    pdf_document = fitz.open(path_pdf)

    highlighted_texts = []

    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        annots = page.annots()

        if annots:
            for annot in annots:
                if annot.type[0] == 8:  # highlight
                    quads = annot.vertices
                    sentences = []
                    for i in range(0, len(quads), 4):
                        rect = fitz.Quad(quads[i:i+4]).rect
                        words = page.get_text("words")  # lista de tuplas
                        # palabras que caen dentro del rectángulo
                        selected = [w[4] for w in words if fitz.Rect(w[:4]).intersects(rect)]
                        sentences.append(" ".join(selected))
                    if sentences:
                        highlighted_texts.append(" ".join(sentences))
    return highlighted_texts
    # Imprimir solo texto limpio


#for i, text in enumerate(highlighted_texts, 1):
#    print(f"Highlight {i}: {text}")

#print(f"\nTotal highlights: {len(highlighted_texts)}")
#print("\n".join(extraer_anotaciones_array("TEORIA2.pdf")))