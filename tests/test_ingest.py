from pathlib import Path

from rag_ingest.ingest import Ingestor


def test_markdown_hierarchy_preserves_sections(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text(
        "# Overview\n\nIntro paragraph.\n\n## Install\n\nStep one.\n",
        encoding="utf-8",
    )

    document = Ingestor().ingest(source)[0]

    assert document.file_type == "md"
    assert len(document.hierarchy.children) == 1
    overview = document.hierarchy.children[0]
    assert overview.title == "Overview"
    assert overview.text == "Intro paragraph."
    assert len(overview.children) == 1
    assert overview.children[0].title == "Install"
    assert overview.children[0].text == "Step one."


def test_plaintext_is_kept_as_single_body_node(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Line one\nLine two\n", encoding="utf-8")

    document = Ingestor().ingest(source)[0]

    assert document.file_type == "text"
    assert document.hierarchy.children[0].node_type == "body"
    assert document.hierarchy.children[0].text == "Line one\nLine two"


def test_html_hierarchy_uses_heading_tags(tmp_path: Path) -> None:
    source = tmp_path / "docs.html"
    source.write_text(
        "<html><body><h1>Guide</h1><p>Intro</p><h2>Usage</h2><p>Run it</p></body></html>",
        encoding="utf-8",
    )

    document = Ingestor().ingest(source)[0]

    assert document.file_type == "html"
    guide = document.hierarchy.children[0]
    assert guide.title == "Guide"
    assert guide.text == "Intro"
    assert guide.children[0].title == "Usage"
    assert guide.children[0].text == "Run it"


def test_pdf_uses_docling_conversion_metadata(tmp_path: Path) -> None:
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    class FakeProv:
        def __init__(self, page_no: int) -> None:
            self.page_no = page_no

    class FakeLabel:
        def __init__(self, value: str) -> None:
            self.value = value

    class TitleItem:
        def __init__(self) -> None:
            self.text = "Manual"
            self.label = FakeLabel("title")
            self.prov = [FakeProv(1)]

    class SectionHeaderItem:
        def __init__(self) -> None:
            self.text = "Details"
            self.level = 1
            self.label = FakeLabel("section_header")
            self.prov = [FakeProv(2)]

    class TextItem:
        def __init__(self, text: str, page_no: int) -> None:
            self.text = text
            self.label = FakeLabel("text")
            self.prov = [FakeProv(page_no)]

    class FakeFormat:
        value = "pdf"

    class FakeInput:
        format = FakeFormat()
        page_count = 2

    class FakeDocument:
        def iterate_items(self):
            yield TitleItem(), 1
            yield TextItem("Intro", 1), 1
            yield SectionHeaderItem(), 1
            yield TextItem("Body", 2), 1

        def export_to_text(self) -> str:
            return "# Manual\n\nIntro\n\n## Details\n\nBody"

    class FakeResult:
        input = FakeInput()
        document = FakeDocument()

    ingestor = Ingestor()
    ingestor._convert_with_docling = lambda path: FakeResult()

    document = ingestor.ingest(source)[0]

    assert document.file_type == "pdf"
    assert document.metadata["page_count"] == 2
    assert document.title == "Manual"
    assert document.hierarchy.children[0].metadata["page_numbers"] == [1]
    assert document.hierarchy.children[0].children[0].metadata["page_numbers"] == [2]
    assert document.hierarchy.children[0].children[0].text == "Body"


def test_us_ac_chunking_splits_and_tracks_parent_context(tmp_path: Path) -> None:
    source = tmp_path / "stories.md"
    source.write_text(
        "Some preamble text.\n\n"
        "**US-1.1 As a user I can log in**\n\nUser story body.\n\n"
        "**AC-1.1 Given valid credentials**\n\nAC body.\n\n"
        "**US-2.1 As an admin I can manage users**\n\nAnother story.\n",
        encoding="utf-8",
    )

    # Chunking is now a separate step driven by the LLM extraction output.
    # For unit tests we provide a fake extractor payload to avoid OpenAI calls.
    class _FakeExtractor:
        def extract(self, markdown_text: str) -> dict:
            return {
                "document_title": source.stem,
                "document_summary": "Test document summary.",
                "document_type": "BRD",
                "metadata": {"epic": "Test epic", "application": "Test app"},
                "stories": [
                    {
                        "id": "US-1.1",
                        "title": "As a user I can log in",
                        "description": "User story body.",
                        "acceptance_criteria": [
                            {
                                "id": "AC-1.1",
                                "title": "Given valid credentials",
                                "criteria": "AC body.",
                            }
                        ],
                        "metadata": {"group": "Test Group", "role": "Test Role"},
                    },
                    {
                        "id": "US-2.1",
                        "title": "As an admin I can manage users",
                        "description": "Another story.",
                        "acceptance_criteria": [],
                        "metadata": {},
                    },
                ],
            }

    from rag_ingest.chunking import chunk_document

    document = Ingestor(extractor=_FakeExtractor()).ingest(source)[0]
    assert document.extracted_json is not None

    chunks_result = chunk_document(document.extracted_json)
    ac_chunks = chunks_result["ac_chunks"]

    # Only acceptance criteria become AC-level chunks.
    assert len(ac_chunks) == 1
    assert ac_chunks[0]["metadata"]["ac_id"] == "AC-1.1"
    assert ac_chunks[0]["metadata"]["story_id"] == "US-1.1"
    assert ac_chunks[0]["metadata"]["group"] == "Test Group"


def test_directory_ingestion_filters_supported_files(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# A", encoding="utf-8")
    (docs_dir / "b.txt").write_text("B", encoding="utf-8")
    (docs_dir / "ignore.csv").write_text("skip", encoding="utf-8")

    documents = Ingestor().ingest(docs_dir)

    assert [Path(document.source_path).name for document in documents] == ["a.md", "b.txt"]
