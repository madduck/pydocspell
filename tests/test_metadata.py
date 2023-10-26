from expecter import expect

from pydocspell import UploadMetadata


def describe_dataclass():
    def with_defaults():
        md = UploadMetadata()
        expect(md.multiple) is False
        expect(md.direction) is None
        expect(md.folder) is None
        expect(md.skipDuplicates) is True
        expect(md.tags) == []
        expect(md.fileFilter) is None
        expect(md.language) is None
        expect(md.attachmentsOnly) is False
        expect(md.flattenArchives) is False

    def with_some_values():
        md = UploadMetadata(tags=["foo"], multiple=True)
        expect(md.tags) == ["foo"]
        expect(md.multiple) is True

    def dict_extraction():
        md = UploadMetadata()
        d = md.as_dict()
        assert "multiple" in d

def describe_docspell_metadata():
    def tags_is_a_nested_string_list():
        tags = ['one', 'two']
        md = UploadMetadata(tags=tags)
        d = md.as_dict()
        assert "items" in d['tags']
        assert d['tags']['items'] == tags
