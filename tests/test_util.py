from expecter import expect

from pydocspell import util


def describe_unique_ids():
    def with_defaults():
        expect(len(util.make_unique_id())) == 47
