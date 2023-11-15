from attrs import define, Factory, asdict
import json

@define(kw_only=True)
class UploadMetadata:
    multiple: bool = False
    direction: (str, type(None)) = None
    folder: (str, type(None)) = None
    skipDuplicates: bool = True
    tags: list[str] = Factory(list)
    fileFilter: (str, type(None)) = None
    language: (str, type(None)) = None
    attachmentsOnly: bool = False
    flattenArchives: bool = False
    customData: (dict, type(None)) = None

    def as_dict(self):
        d = asdict(self)
        tags = d.get('tags')
        d['tags'] = {'items': tags}
        return d

    def items(self):
        return self.as_dict().items()

    def to_json(self, **kwargs):
        return json.dumps(self.as_dict())
